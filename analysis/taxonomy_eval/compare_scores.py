"""Score both pilot clients with the old (v0) and current taxonomy; report what moved.
Usage: python analysis/taxonomy_eval/compare_scores.py"""
import sqlite3, sys, yaml
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from prospector import db
from prospector.config import load_client, load_model, load_taxonomy
from prospector.score import score_client

con = db.connect(ROOT / "data" / "prospector.db")
v0 = yaml.safe_load(open(Path(__file__).parent / "taxonomy_v0.yaml"))
v1 = load_taxonomy()
for cid in ["nyspha", "appius"]:
    client, model = load_client(cid), load_model()
    a, b = score_client(con, client, model, v0), score_client(con, client, model, v1)
    pa = {p["ein"]: p for p in a["prospects"]}
    pb = {p["ein"]: p for p in b["prospects"]}
    print(f"\n=== {cid}: {len(pb)} scored funders")
    print("  tiers v0:", dict(sorted(Counter(p["tier"] for p in pa.values()).items())))
    print("  tiers v1:", dict(sorted(Counter(p["tier"] for p in pb.values()).items())))
    moves = Counter((pa[e]["tier"], pb[e]["tier"]) for e in pb if pa[e]["tier"] != pb[e]["tier"])
    print("  tier moves:", dict(moves))
    d = sorted(((pb[e]["score"] - pa[e]["score"], e) for e in pb), key=lambda x: x[0])
    print(f"  mean score change {sum(x for x, _ in d) / len(d):+.2f}; vague-flagged v0={sum('vague_purpose' in str(p.get('flags')) for p in pa.values())} v1={sum('vague_purpose' in str(p.get('flags')) for p in pb.values())}")
    for delta, e in d[:5] + d[-5:]:
        print(f"    {delta:+6.1f}  {pa[e]['score']:5.1f} -> {pb[e]['score']:5.1f}  {pb[e]['tier']:5} {pb[e]['name'][:45]:45} themes v1: {pb[e].get('top_themes','')}")
    print("  top 10 v1:")
    for p in sorted(pb.values(), key=lambda p: -p["score"])[:10]:
        print(f"    {p['score']:5.1f} {p['tier']:5} (v0 {pa[p['ein']]['score']:5.1f})  {p['name'][:45]:45} {p.get('top_themes','')}")
    print("  validation seeds:", [(v.get("seed"), v.get("tier") or v.get("status")) for v in b["validation"]])
