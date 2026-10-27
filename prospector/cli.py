"""Command line: python -m prospector <command> ...

Typical first run on real data:
  python scripts/get_reference.py                      # BMF + Census files
  (download the USDA RUCA ZIP file by hand into data/reference/)
  python -m prospector load-reference
  python -m prospector index --year 2025               # how many 990-PFs are listed?
  python -m prospector download --url <monthly zip URL>
  python -m prospector ingest data/raw/<zip>
  python -m prospector match
  python -m prospector report --client nyspha

Quarterly refresh (Appius can run this without the team):
  python -m prospector refresh --client nyspha --zips data/raw/*.zip

Offline demo on synthetic data (no downloads):
  python -m prospector demo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prospector import db, grantsgov, irs, match, reference, report
from prospector.config import ROOT, load_client, load_model, load_taxonomy
from prospector.score import score_client

DATA = ROOT / "data"
DEFAULT_DB = DATA / "prospector.db"
REF = DATA / "reference"
RAW = DATA / "raw"
OUT = ROOT / "outputs"
FIXTURES = ROOT / "tests" / "fixtures"


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_index(a):
    path = irs.download(irs.index_url(a.year), RAW)
    counts = irs.summarize_index(path)
    print(f"IRS index {a.year} (processing year, not tax year): {path}")
    _print(counts)
    print(f"990-PF returns listed: {counts.get('990PF', 0):,}")


def cmd_download(a):
    print(irs.download(a.url, RAW))


def cmd_ingest(a):
    con = db.connect(a.db)
    for z in a.zips:
        stats = irs.ingest_zip(con, Path(z), limit=a.limit)
        print(Path(z).name, stats)
    print("Parse warnings are in the parse_log table:  python -m prospector warnings")


def cmd_warnings(a):
    con = db.connect(a.db)
    for r in con.execute("SELECT source, object_id, level, message FROM parse_log ORDER BY id DESC LIMIT ?",
                         (a.n,)):
        print(dict(r))


def cmd_load_reference(a):
    con = db.connect(a.db)
    bmf = sorted(REF.glob("eo_*.csv"))
    if bmf:
        print("BMF rows:", reference.load_bmf(con, bmf))
    else:
        print("No BMF files in data/reference (run scripts/get_reference.py)")
    zcta = REF / "tab20_zcta520_county20_natl.txt"
    if zcta.exists():
        print("ZIP-to-county rows:", reference.load_zcta_county(con, zcta))
    ruca = sorted(list(REF.glob("*RUCA*")) + list(REF.glob("*ruca*")))
    if ruca:
        print("RUCA rows:", reference.load_ruca(con, ruca[0]))
    else:
        print("No RUCA file found. Download the ZIP-code RUCA file from USDA ERS into data/reference/.")


def cmd_match(a):
    con = db.connect(a.db)
    model = load_model()
    print(match.run_matching(con, model["matching"]["fuzzy_threshold"], rematch=a.rematch))
    _print(match.match_rate(con))


def cmd_match_sample(a):
    import csv

    con = db.connect(a.db)
    rows = match.sample_for_review(con, a.n)
    OUT.mkdir(exist_ok=True)
    path = OUT / "match_review_sample.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["correct?"] if rows else ["empty"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} matches to hand-check: {path}")


def run_client(con, client_id, offline_federal=None, out_dir=OUT, federal=True):
    model, taxonomy, client = load_model(), load_taxonomy(), load_client(client_id)
    result = score_client(con, client, model, taxonomy)
    fed = []
    if federal:
        try:
            fed = grantsgov.search_client(client, cache_dir=DATA / "cache" / "grantsgov",
                                          offline_payloads=offline_federal)
        except Exception as exc:  # network trouble shouldn't sink the foundation list
            print(f"Grants.gov search skipped: {exc}", file=sys.stderr)
    path = report.write_report(client, result, fed, out_dir, match.match_rate(con))
    return result, fed, path


def _summary(client_id, result, fed, path):
    tiers = {}
    for p in result["prospects"]:
        tiers[p["tier"]] = tiers.get(p["tier"], 0) + 1
    print(f"\n== {client_id}: {len(result['prospects'])} scored, {len(result['dropped'])} dropped, tiers {tiers}")
    for p in result["prospects"][:10]:
        print(f"  {p['rank']:>3}. {p['tier']:<5} {p['score']:>5}  {p['name']}  [{p['flags']}]")
    for v in result["validation"]:
        print(f"  seed: {v['seed']}: {v['status']}")
    if result.get("grantee_leads"):
        print(f"  grantee leads (internal): {len(result['grantee_leads'])}")
    print(f"  federal opportunities: {len(fed)}")
    print(f"  report: {path}")


def cmd_report(a):
    con = db.connect(a.db)
    result, fed, path = run_client(con, a.client, federal=not a.no_federal)
    _summary(a.client, result, fed, path)


def cmd_refresh(a):
    """Rebuild a client's list from fresh IRS data: ingest new zips, re-match, score, report."""
    con = db.connect(a.db)
    for z in a.zips or []:
        print(Path(z).name, irs.ingest_zip(con, Path(z)))
    model = load_model()
    print(match.run_matching(con, model["matching"]["fuzzy_threshold"]))
    for cid in a.client:
        result, fed, path = run_client(con, cid, federal=not a.no_federal)
        _summary(cid, result, fed, path)


def cmd_demo(a):
    """Everything end to end on the synthetic fixtures. No network."""
    demo_db = DATA / "demo.db"
    demo_db.unlink(missing_ok=True)
    con = db.connect(demo_db)
    print("BMF rows:", reference.load_bmf(con, [FIXTURES / "bmf_fixture.csv"]))
    print("ZIP-to-county rows:", reference.load_zcta_county(con, FIXTURES / "zcta_county_fixture.txt"))
    print("RUCA rows:", reference.load_ruca(con, FIXTURES / "ruca_fixture.csv"))
    print("Ingest:", irs.ingest_xml_files(con, sorted((FIXTURES / "xml").glob("*.xml"))))
    model = load_model()
    print("Match:", match.run_matching(con, model["matching"]["fuzzy_threshold"]))
    _print(match.match_rate(con))
    payloads = json.loads((FIXTURES / "grantsgov_fixture.json").read_text())
    for cid in ("nyspha", "appius"):
        result, fed, path = run_client(con, cid, offline_federal=payloads, out_dir=OUT / "demo")
        _summary(cid, result, fed, path)
    print("\nDemo data is SYNTHETIC. Validation seeds show 'not in data yet' until you load real IRS files.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="prospector", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite file (default data/prospector.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("index", help="download a yearly IRS index and count return types")
    s.add_argument("--year", type=int, required=True)
    s.set_defaults(fn=cmd_index)

    s = sub.add_parser("download", help="download an IRS monthly zip (cached)")
    s.add_argument("--url", required=True)
    s.set_defaults(fn=cmd_download)

    s = sub.add_parser("ingest", help="parse IRS zip(s) into the database")
    s.add_argument("zips", nargs="+")
    s.add_argument("--limit", type=int, help="stop after N saved returns (for testing)")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("warnings", help="show recent parse warnings")
    s.add_argument("-n", type=int, default=50)
    s.set_defaults(fn=cmd_warnings)

    s = sub.add_parser("load-reference", help="load BMF, Census and RUCA files from data/reference")
    s.set_defaults(fn=cmd_load_reference)

    s = sub.add_parser("match", help="match grant recipients to the BMF")
    s.add_argument("--rematch", action="store_true")
    s.set_defaults(fn=cmd_match)

    s = sub.add_parser("match-sample", help="write a sample of matches to hand-check")
    s.add_argument("--n", type=int, default=50)
    s.set_defaults(fn=cmd_match_sample)

    s = sub.add_parser("report", help="score one client and write its Excel file")
    s.add_argument("--client", required=True)
    s.add_argument("--no-federal", action="store_true")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("refresh", help="ingest new zips, re-match, and rebuild client lists")
    s.add_argument("--client", nargs="+", required=True)
    s.add_argument("--zips", nargs="*")
    s.add_argument("--no-federal", action="store_true")
    s.set_defaults(fn=cmd_refresh)

    s = sub.add_parser("demo", help="run end to end on synthetic fixtures (no network)")
    s.set_defaults(fn=cmd_demo)

    a = p.parse_args(argv)
    a.fn(a)
    return 0
