"""Match grant recipients to the IRS Business Master File.

990-PF grant lines carry no recipient EIN, so matching goes:
  1. EIN (Schedule I lines that include one)
  2. exact normalized name in the same state (and city, when that breaks a tie)
  3. fuzzy name within the same state and city, at or above the threshold

A wrong match is worse than no match. Hand-check a sample with
`python -m prospector match-sample --n 50` and record accuracy.
"""
from __future__ import annotations

from collections import defaultdict

from prospector.names import normalize, similarity


def run_matching(con, threshold: float = 90, rematch: bool = False) -> dict:
    if rematch:
        con.execute("DELETE FROM matches")
    bmf_by_ein = {r["ein"] for r in con.execute("SELECT ein FROM bmf")}
    by_state_norm = defaultdict(list)
    by_state_city = defaultdict(list)
    for r in con.execute("SELECT ein, norm_name, state, city FROM bmf"):
        by_state_norm[(r["state"], r["norm_name"])].append((r["ein"], (r["city"] or "").upper()))
        by_state_city[(r["state"], (r["city"] or "").upper())].append((r["ein"], r["norm_name"]))

    pending = con.execute(
        "SELECT g.grant_id, g.recipient_name, g.recipient_ein, g.state, g.city FROM grants g "
        "LEFT JOIN matches m ON m.grant_id = g.grant_id WHERE m.grant_id IS NULL").fetchall()
    out = []
    stats = {"ein": 0, "exact": 0, "fuzzy": 0, "none": 0}
    for g in pending:
        state = (g["state"] or "").upper()
        city = (g["city"] or "").upper()
        if g["recipient_ein"] and g["recipient_ein"] in bmf_by_ein:
            out.append((g["grant_id"], g["recipient_ein"], 100.0, "ein"))
            stats["ein"] += 1
            continue
        norm = normalize(g["recipient_name"])
        cands = by_state_norm.get((state, norm), [])
        if len(cands) > 1:
            same_city = [c for c in cands if c[1] == city]
            cands = same_city if len(same_city) == 1 else cands
        if len(cands) == 1:
            out.append((g["grant_id"], cands[0][0], 100.0, "exact"))
            stats["exact"] += 1
            continue
        best = None
        for ein, cand_norm in by_state_city.get((state, city), []):
            s = similarity(norm, cand_norm)
            if s >= threshold and (best is None or s > best[1]):
                best = (ein, s)
        if best:
            out.append((g["grant_id"], best[0], best[1], "fuzzy"))
            stats["fuzzy"] += 1
        else:
            out.append((g["grant_id"], None, 0.0, "none"))
            stats["none"] += 1
    con.executemany("INSERT OR REPLACE INTO matches VALUES (?,?,?,?)", out)
    con.commit()
    return stats


def match_rate(con, state: str = "NY") -> dict:
    """Share of grant dollars to `state` recipients that matched the BMF."""
    row = con.execute(
        "SELECT SUM(g.amount) AS total, SUM(CASE WHEN m.bmf_ein IS NOT NULL THEN g.amount END) AS matched "
        "FROM grants g LEFT JOIN matches m ON m.grant_id = g.grant_id WHERE g.state = ?", (state,)).fetchone()
    total, matched = row["total"] or 0, row["matched"] or 0
    return {"state": state, "dollars": total, "matched_dollars": matched,
            "match_rate": (matched / total) if total else None, "target": 0.60}


def sample_for_review(con, n: int = 50, seed: int = 7) -> list[dict]:
    """Random matched grants to hand-check. Fill the 'correct?' column yourself."""
    rows = con.execute(
        "SELECT g.recipient_name, g.city, g.state, m.method, m.score, b.name AS bmf_name, b.city AS bmf_city, "
        "b.ntee FROM grants g JOIN matches m ON m.grant_id = g.grant_id JOIN bmf b ON b.ein = m.bmf_ein "
        "WHERE m.method IN ('exact','fuzzy') ORDER BY (g.grant_id * ? ) % 1000003 LIMIT ?", (seed, n)).fetchall()
    return [dict(r) for r in rows]
