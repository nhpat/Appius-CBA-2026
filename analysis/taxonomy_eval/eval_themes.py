"""Measure config/taxonomy.yaml against hand-labeled grant lines.

  python analysis/taxonomy_eval/eval_themes.py                     # current taxonomy
  python analysis/taxonomy_eval/eval_themes.py --taxonomy old.yaml # any other version
  python analysis/taxonomy_eval/eval_themes.py --set holdout       # untuned holdout lines
  python analysis/taxonomy_eval/eval_themes.py --audit             # + full-DB trigger audit

Inputs: sample.csv (drawn by sample_lines.py) and labels.csv (hand labels; see
LABELING.md). Uses ThemeTagger exactly as score.py does: tag(purpose,
recipient_name, ntee) with ntee from the matched BMF record.
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from prospector.themes import ThemeTagger, _norm  # noqa: E402


SETS = {"main": ("sample.csv", "labels.csv"), "holdout": ("holdout.csv", "holdout_labels.csv")}


def load(taxonomy_path, which="main"):
    tax = yaml.safe_load(open(taxonomy_path))
    names = [which] if which != "all" else ["main", "holdout"]
    rows = []
    for n in names:
        rows += _load_set(*SETS[n])
    return tax, rows


def _load_set(sample_file, label_file):
    labels = {r["id"]: r for r in csv.DictReader(open(HERE / label_file))}
    rows = []
    for r in csv.DictReader(open(HERE / sample_file)):
        lab = labels[r["id"]]
        r["gold"] = {t for t in lab["gold_themes"].split(";") if t}
        r["generic"] = lab["generic_purpose"] == "Y"
        r["note"] = lab["note"]
        r["amount"] = float(r["amount"])
        rows.append(r)
    return rows


def triggers(tagger, theme, purpose, recipient, ntee):
    """Which rule(s) put this theme on the line. Mirrors ThemeTagger.tag()."""
    spec = tagger.themes[theme]
    text = re.sub(" +", " ", f" {_norm(purpose)} {_norm(recipient)} ")
    for x in spec["exclude"]:
        text = text.replace(x, " ")
    hits = [f'kw "{k.strip()}"' for k in spec["keywords"] if k in text]
    if not hits and ntee and any(ntee.upper().startswith(p) for p in spec["ntee"]):
        hits = [f"ntee {ntee}"]
    return hits


def prf(rows, theme):
    tp = sum(theme in r["pred"] and theme in r["gold"] for r in rows)
    fp = sum(theme in r["pred"] and theme not in r["gold"] for r in rows)
    fn = sum(theme not in r["pred"] and theme in r["gold"] for r in rows)
    p = tp / (tp + fp) if tp + fp else None
    rc = tp / (tp + fn) if tp + fn else None
    return tp, fp, fn, p, rc


def fmt(x):
    return "  -  " if x is None else f"{x:5.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", default=ROOT / "config" / "taxonomy.yaml")
    ap.add_argument("--set", default="main", choices=["main", "holdout", "all"],
                    help="main = 240 lines the revision was tuned on; holdout = 100 fresh lines")
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()
    tax, rows = load(a.taxonomy, a.set)
    tagger = ThemeTagger(tax)
    for r in rows:
        r["pred"] = tagger.tag(r["purpose"], r["recipient_name"], r["ntee"] or None)
        r["vague"] = tagger.is_vague(r["purpose"], r["recipient_name"], r["ntee"] or None)

    print(f"Taxonomy: {Path(a.taxonomy).resolve().relative_to(ROOT)}\nLines: {len(rows)} "
          f"({Counter(r['stratum'] for r in rows)})\n")
    print("Per-theme precision / recall (all strata | random stratum only)")
    print(f"{'theme':20} {'gold':>4} {'tp':>3} {'fp':>3} {'fn':>3} {'prec':>5} {'rec':>5}"
          f"  | {'gold':>4} {'prec':>5} {'rec':>5}")
    rand = [r for r in rows if r["stratum"] == "random"]
    tot = Counter()
    for t in tax["themes"]:
        tp, fp, fn, p, rc = prf(rows, t)
        tot.update(tp=tp, fp=fp, fn=fn)
        _, _, _, p2, r2 = prf(rand, t)
        g2 = sum(t in r["gold"] for r in rand)
        print(f"{t:20} {tp + fn:4} {tp:3} {fp:3} {fn:3} {fmt(p)} {fmt(rc)}  | {g2:4} {fmt(p2)} {fmt(r2)}")
    mp = tot["tp"] / (tot["tp"] + tot["fp"]) if tot["tp"] + tot["fp"] else 0
    mr = tot["tp"] / (tot["tp"] + tot["fn"]) if tot["tp"] + tot["fn"] else 0
    print(f"{'micro (all themes)':20} {tot['tp'] + tot['fn']:4} {tot['tp']:3} {tot['fp']:3} {tot['fn']:3} "
          f"{mp:5.2f} {mr:5.2f}")
    exact = sum(r["pred"] == r["gold"] for r in rows)
    print(f"Lines where predicted theme set == gold set: {exact}/{len(rows)}\n")

    print("WRONG tags (false positives) and the rule that fired")
    fp_rules = Counter()
    for r in rows:
        for t in sorted(r["pred"] - r["gold"]):
            why = triggers(tagger, t, r["purpose"], r["recipient_name"], r["ntee"])
            fp_rules.update((t, w) for w in why)
            print(f"  #{r['id']:>3} {t:18} {', '.join(why):28} | {r['recipient_name'][:38]:38} | {r['purpose'][:45]}")
    print("\n  FP count by rule:")
    for (t, w), n in fp_rules.most_common():
        print(f"    {n:3}  {t:18} {w}")

    print("\nMISSED tags (false negatives)")
    for r in rows:
        for t in sorted(r["gold"] - r["pred"]):
            print(f"  #{r['id']:>3} {t:18} ntee={r['ntee'] or '-':6} | {r['recipient_name'][:40]:40} | {r['purpose'][:50]}")

    print("\nis_vague() checks")
    gen = [r for r in rows if r["generic"]]
    gen_nothemes = [r for r in gen if not r["gold"]]
    print(f"  Lines whose purpose is boilerplate (gold): {len(gen)}")
    bad = [r for r in gen_nothemes if r["pred"]]
    print(f"  (a) boilerplate purpose + no real theme, but tagger added a theme: {len(bad)}/{len(gen_nothemes)}")
    for r in bad:
        print(f"      #{r['id']:>3} {sorted(r['pred'])} | {r['recipient_name'][:40]} | {r['purpose'][:40]}")
    noinfo = [r for r in gen_nothemes if not r["ntee"]]
    miss_v = [r for r in noinfo if not r["vague"] and not r["pred"]]
    print(f"  (b) boilerplate purpose, no theme, no NTEE -> should be vague (0.25): "
          f"{len(noinfo) - len(miss_v)}/{len(noinfo)} are; NOT vague (scored 0 instead):")
    for r in miss_v:
        print(f"      #{r['id']:>3} \"{r['purpose'][:60]}\"")
    themed_vague = [r for r in rows if r["gold"] and r["vague"]]
    print(f"  (c) real-theme lines that fell through as vague: {len(themed_vague)}/"
          f"{sum(bool(r['gold']) for r in rows)}")
    for r in themed_vague:
        print(f"      #{r['id']:>3} {sorted(r['gold'])} | {r['recipient_name'][:40]} | {r['purpose'][:40]}")
    spec_vague = [r for r in rows if not r["generic"] and r["vague"]]
    print(f"  (d) specific (non-boilerplate) purpose judged vague: {len(spec_vague)}")
    for r in spec_vague:
        print(f"      #{r['id']:>3} \"{r['purpose'][:60]}\"")

    if a.audit:
        audit(tax, tagger)


def audit(tax, tagger):
    """Every grant line in the DB to NY + neighbors: which rule drives each theme's dollars."""
    con = sqlite3.connect(ROOT / "data" / "prospector.db")
    con.row_factory = sqlite3.Row
    q = """SELECT g.purpose, g.recipient_name, g.amount, b.ntee FROM grants g
           LEFT JOIN matches m ON m.grant_id = g.grant_id LEFT JOIN bmf b ON b.ein = m.bmf_ein
           WHERE g.state IN ('NY','NJ','PA','CT','MA','VT')"""
    lines = [dict(r) for r in con.execute(q)]
    # One $825M "see attached list" line with no purpose would swamp every share.
    lines = [l for l in lines if (l["amount"] or 0) < 100_000_000]
    total = sum(l["amount"] or 0 for l in lines)
    print(f"\nFULL-DB AUDIT: {len(lines):,} lines to NY+neighbors, ${total:,.0f} (lines over $100M excluded)")
    vague_d = sum(l["amount"] or 0 for l in lines
                  if not tagger.tag(l["purpose"], l["recipient_name"], l["ntee"])
                  and tagger.is_vague(l["purpose"], l["recipient_name"], l["ntee"]))
    print(f"  dollars scored vague (0.25): {vague_d / total:.1%}")
    for t in tax["themes"]:
        by = defaultdict(lambda: [0, 0.0])
        n = d = 0
        for l in lines:
            why = triggers(tagger, t, l["purpose"], l["recipient_name"], l["ntee"])
            if not why:
                continue
            n += 1
            d += l["amount"] or 0
            key = why[0] if why[0].startswith("kw") else "ntee " + (l["ntee"] or "")[:3]
            by[key][0] += 1
            by[key][1] += l["amount"] or 0
        print(f"\n  {t}: {n:,} lines, ${d:,.0f} ({d / total:.1%} of dollars). Top rules by $:")
        for k, (c, dd) in sorted(by.items(), key=lambda kv: -kv[1][1])[:6]:
            print(f"    {k:30} {c:6,} lines  ${dd:>14,.0f}")


if __name__ == "__main__":
    main()
