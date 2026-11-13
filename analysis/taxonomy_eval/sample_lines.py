"""Draw the hand-labeling sample of grant purpose lines from data/prospector.db.

Frame: grant lines to recipients in NY + neighbor states (what mission scoring
mostly sees). At most 2 lines per funder so one foundation's 100 identical
scholarship lines can't dominate.
  - 140 lines: simple random from the frame (unbiased precision / vague rate)
  - 40 lines:  "targeted" pool using words close to the client themes (substance
               use, agriculture, rural, workforce). These overlap the taxonomy
               keywords, so recall on this stratum is optimistic; report it apart.
  - 60 lines:  random from an "enriched" pool whose purpose or recipient mentions
               a health / food / farm / youth / housing word, so every theme has
               enough positives to estimate recall. Enrichment words were chosen
               to be broader than the taxonomy keywords.
Usage: python analysis/taxonomy_eval/sample_lines.py > analysis/taxonomy_eval/sample.csv
       python analysis/taxonomy_eval/sample_lines.py --holdout > analysis/taxonomy_eval/holdout.csv
--holdout draws 70 random + 30 targeted NEW lines (excluding sample.csv), labeled
before the revised taxonomy was run on them, to measure the revision honestly.
"""
import csv, random, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
con = sqlite3.connect(ROOT / "data" / "prospector.db")
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute("""
    SELECT g.grant_id, g.funder_ein, g.recipient_name, g.state, g.purpose, g.amount, b.ntee
    FROM grants g LEFT JOIN matches m ON m.grant_id = g.grant_id
    LEFT JOIN bmf b ON b.ein = m.bmf_ein
    WHERE g.state IN ('NY','NJ','PA','CT','MA','VT') AND COALESCE(TRIM(g.purpose),'') <> ''""")]
ENRICH = ["health", "hospital", "medic", "clinic", "nurs", "mental", "drug", "food", "farm",
          "agricult", "rural", "youth", "child", "housing", "homeless", "hunger", "cancer", "family"]
HOLDOUT = "--holdout" in sys.argv
if HOLDOUT:
    used = {int(r["grant_id"]) for r in csv.DictReader(open(Path(__file__).parent / "sample.csv"))}
    rows = [r for r in rows if r["grant_id"] not in used]
rng = random.Random(7 if HOLDOUT else 2026)
rng.shuffle(rows)

def take(pool, n, seen, per_funder):
    out = []
    for r in pool:
        if len(out) == n:
            break
        if r["grant_id"] in seen or per_funder.get(r["funder_ein"], 0) >= 2:
            continue
        seen.add(r["grant_id"]); per_funder[r["funder_ein"]] = per_funder.get(r["funder_ein"], 0) + 1
        out.append(r)
    return out

seen, pf = set(), {}
rand = take(rows, 70 if HOLDOUT else 140, seen, pf)
enr_pool = [r for r in rows if any(w in f"{r['purpose']} {r['recipient_name']}".lower() for w in ENRICH)]
enr = take(enr_pool, 0 if HOLDOUT else 60, seen, pf)
TARGET = ["drug", "sober", "rehab", "detox", "psych", "opioid", "addict", "recovery", "mental",
          "grower", "crop", "livestock", "harvest", "agricult", "farm", "rural", "nurs",
          "medical school", "physician", "workforce", "public health", "coalition", "advocacy",
          "policy", "community health"]
tgt_pool = [r for r in rows if any(w in f"{r['purpose']} {r['recipient_name']}".lower() for w in TARGET)]
tgt = take(tgt_pool, 30 if HOLDOUT else 40, seen, pf)
w = csv.writer(sys.stdout)
w.writerow(["id", "stratum", "grant_id", "recipient_name", "state", "ntee", "amount", "purpose"])
for i, (s, r) in enumerate([("random", r) for r in rand] + [("enriched", r) for r in enr] + [("targeted", r) for r in tgt], 1):
    w.writerow([f"h{i}" if HOLDOUT else i, s, r["grant_id"], r["recipient_name"], r["state"], r["ntee"] or "", r["amount"], " ".join(r["purpose"].split())])
