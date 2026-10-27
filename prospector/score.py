"""Score every funder against a client profile.

Read config/model.yaml alongside this file: every number used here comes from
there. Three rules:
  1. Missing data is never scored as zero. It gets a neutral value and a flag.
  2. Validation seeds test the model; they are never used to score.
  3. Write down every weight change and why (docs/MODEL_CHANGELOG.md).
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

from prospector.config import clean_county, county_bucket, is_upstate_ny
from prospector.names import normalize, similarity
from prospector.themes import ThemeTagger


# --------------------------------------------------------------------------- data
def data_years(con, window: int) -> list[int]:
    row = con.execute("SELECT MAX(tax_year) FROM filings").fetchone()
    latest = row[0]
    if latest is None:
        return []
    return list(range(latest - window + 1, latest + 1))


def load_grants(con, years: list[int]) -> list[dict]:
    q = f"""
        SELECT g.*, m.bmf_ein, m.method AS match_method, b.ntee, b.revenue AS recipient_revenue,
               b.name AS bmf_name, zg.county_name, zg.ruca,
               COALESCE(zb.county_name, zg.county_name) AS bmf_county
        FROM grants g
        LEFT JOIN matches m ON m.grant_id = g.grant_id
        LEFT JOIN bmf b ON b.ein = m.bmf_ein
        LEFT JOIN zip_geo zg ON zg.zip = g.zip
        LEFT JOIN zip_geo zb ON zb.zip = b.zip
        WHERE g.tax_year IN ({','.join('?' * len(years))})
    """
    return [dict(r) for r in con.execute(q, years)]


def load_filings(con) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in con.execute("SELECT * FROM filings ORDER BY tax_year"):
        out[r["ein"]].append(dict(r))
    return out


# ------------------------------------------------------------------ components
def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def mission_score(lines, client, tagger, cfg):
    in_state = [g for g in lines if (g["state"] or "").upper() in client["primary_states"]]
    use = in_state if len(in_state) >= cfg["in_state_min_grants"] else lines
    total = sum(g["amount"] for g in use)
    flags, theme_dollars = [], defaultdict(float)
    if total <= 0:
        return cfg["vague_neutral"], ["no_grant_detail"], {}
    known_d = known_v = vague_d = 0.0
    for g in use:
        themes = tagger.tag(g["purpose"], g["recipient_name"], g["ntee"])
        for t in themes:
            theme_dollars[t] += g["amount"]
        if not themes and tagger.is_vague(g["purpose"], g["recipient_name"], g["ntee"]):
            vague_d += g["amount"]
            continue
        known_d += g["amount"]
        known_v += g["amount"] * tagger.value(themes, client["theme_weights"])
    known = known_v / known_d if known_d else 0.0
    score = (known_v + vague_d * cfg["vague_neutral"]) / total
    if vague_d / total > cfg["vague_flag_share"]:
        flags.append("vague_purpose")
    shares = {t: d / total for t, d in theme_dollars.items()}
    return min(1.0, score), flags, shares


def geography_score(lines, client, cfg):
    total = sum(g["amount"] for g in lines)
    if total <= 0:
        return 0.0, [], {}
    prim = sum(g["amount"] for g in lines if (g["state"] or "").upper() in client["primary_states"])
    sec = sum(g["amount"] for g in lines if (g["state"] or "").upper() in client["secondary_states"])
    state_share = (prim + 0.5 * sec) / total
    state_part = min(1.0, state_share / cfg["state_full_share"])

    flags = []
    focus = secondary = 0.0
    for g in lines:
        b = county_bucket(client, g["state"], g["county_name"] or g["bmf_county"])
        if b == "focus":
            focus += g["amount"]
        elif b == "secondary":
            secondary += g["amount"]
    region_share = (focus + 0.5 * secondary) / total
    region_part = min(1.0, region_share / cfg["region_full_share"])

    ruca_known = [g for g in lines if g["ruca"] is not None]
    known_d = sum(g["amount"] for g in ruca_known)
    if known_d < 0.5 * total:
        rural_part = cfg["rural_missing_value"]
        flags.append("rural_data_missing")
        rural_share = None
    else:
        rural_d = sum(g["amount"] for g in ruca_known if g["ruca"] >= cfg["rural_ruca_min"])
        rural_share = rural_d / known_d
        rural_part = min(1.0, rural_share / cfg["rural_full_share"])

    p = cfg["parts"]
    if client["focus_counties"]:
        score = p["state"] * state_part + p["region"] * region_part + p["rural"] * rural_part
    else:  # statewide client: region folds into state
        score = (p["state"] + p["region"]) * state_part + p["rural"] * rural_part
    detail = {"primary_state_share": prim / total, "focus_county_share": focus / total,
              "rural_share": rural_share}
    return score, flags, detail


def size_score(lines, client, cfg):
    in_state = [g for g in lines if (g["state"] or "").upper() in client["primary_states"]]
    use = in_state or lines
    med = _median([g["amount"] for g in use])
    low, high = client["ask_band"]["low"], client["ask_band"]["high"]
    flags = []
    if med is None:
        grant_part = 0.5
    elif low <= med <= high:
        grant_part = 1.0
    elif med < low:
        grant_part = med / low
    else:
        grant_part = high / med
        if med > 2 * high:
            flags.append("oversized_hand_review")

    revs = {}
    for g in use:
        if g["bmf_ein"] and g["recipient_revenue"] is not None:
            revs[g["bmf_ein"]] = g["recipient_revenue"]
    med_rev = _median(list(revs.values()))
    target = cfg["grantee_multiple"] * client["capacity_budget"]
    if med_rev is None:
        grantee_part = cfg["grantee_missing_value"]
        flags.append("grantee_size_unknown")
    else:
        grantee_part = 1.0 if med_rev <= target else target / med_rev
    p = cfg["parts"]
    return p["grant"] * grant_part + p["grantee"] * grantee_part, flags, {"median_grant": med,
                                                                         "median_grantee_revenue": med_rev}


def peer_score(lines, client, cfg):
    peers = [normalize(p) for p in client["peers"]]
    recips = {normalize(g["bmf_name"] or g["recipient_name"]) for g in lines}
    recips |= {normalize(g["recipient_name"]) for g in lines}
    hit = set()
    for i, p in enumerate(peers):
        if any(similarity(p, r) >= cfg["fuzzy_threshold"] for r in recips if r):
            hit.add(client["peers"][i])
    n = len(hit)
    return (cfg["two_plus"] if n >= 2 else cfg["one_match"] if n == 1 else 0.0), sorted(hit)


def openness_score(lines, latest_filing, cfg):
    flags = []
    if latest_filing.get("preselected_only"):
        return cfg["preselected_value"], ["preselected_only"], None
    score = cfg["base"]
    if latest_filing.get("application_text"):
        score += cfg["application_bonus"]
    by_year = defaultdict(set)
    for g in lines:
        by_year[g["tax_year"]].add(normalize(g["recipient_name"]))
    years = sorted(by_year)
    if len(years) < 2:
        rate = cfg["single_year_assumed_rate"]
        flags.append("new_grantee_rate_assumed")
    else:
        latest = by_year[years[-1]]
        earlier = set().union(*(by_year[y] for y in years[:-1]))
        rate = len(latest - earlier) / len(latest) if latest else 0.0
    score += cfg["new_grantee_bonus"] * min(1.0, rate / cfg["new_grantee_full_rate"])
    return min(1.0, score), flags, rate


def activity_score(giving_by_year, latest_data_year, cfg):
    years = sorted(giving_by_year)
    avg = sum(giving_by_year.values()) / len(years) if years else 0.0
    level = min(1.0, math.sqrt(avg / cfg["level_full_giving"])) if avg > 0 else 0.0
    if len(years) >= 2:
        prior = [giving_by_year[y] for y in years[:-1]]
        trend = 1.0 if giving_by_year[years[-1]] >= cfg["trend_ratio"] * (sum(prior) / len(prior)) else 0.0
    else:
        trend = 0.5
    recency = 1.0 if years and years[-1] >= latest_data_year else 0.0
    p = cfg["parts"]
    return p["level"] * level + p["trend"] * trend + p["recency"] * recency, avg


def tier_for(score: float, tiers: dict) -> str:
    for name, minimum in sorted(tiers.items(), key=lambda kv: -kv[1]):
        if score >= minimum:
            return name
    return "Watch"


# ------------------------------------------------------------------ main entry
def score_client(con, client: dict, model: dict, taxonomy: dict) -> dict:
    """Return {'prospects': [...], 'dropped': [...], 'validation': [...], 'meta': {...}}"""
    years = data_years(con, model["window_years"])
    if not years:
        return {"prospects": [], "dropped": [], "validation": [], "grantee_leads": [], "meta": {"years": []}}
    latest_year = years[-1]
    grants = load_grants(con, years)
    filings = load_filings(con)
    tagger = ThemeTagger(taxonomy)
    hf = model["hard_filters"]
    w = model["weights"]

    by_funder = defaultdict(list)
    for g in grants:
        by_funder[g["funder_ein"]].append(g)

    prospects, dropped = [], []
    client_ein = (client.get("ein") or "").replace("-", "")
    for ein, fl in filings.items():
        if ein == client_ein:
            continue
        lines = by_funder.get(ein, [])
        latest = fl[-1]
        name = latest["name"]
        giving = defaultdict(float)
        for g in lines:
            giving[g["tax_year"]] += g["amount"]
        for f in fl:  # count filed years with zero itemized grants as zero giving
            if f["tax_year"] in years:
                giving.setdefault(f["tax_year"], 0.0)
        avg_giving = sum(giving.values()) / len(giving) if giving else 0.0

        reason = None
        if latest_year - latest["tax_year"] > hf["max_years_since_filing"]:
            reason = f"no filing since {latest['tax_year']}"
        elif avg_giving < hf["min_avg_annual_giving"]:
            reason = f"average giving ${avg_giving:,.0f} under ${hf['min_avg_annual_giving']:,.0f}"
        elif hf["require_primary_state_grant"] and not any(
                (g["state"] or "").upper() in client["primary_states"] for g in lines):
            reason = "no grants in " + "/".join(client["primary_states"])
        elif hf.get("drop_preselected_only") and latest.get("preselected_only"):
            reason = "preselected only"
        if reason:
            dropped.append({"ein": ein, "name": name, "reason": reason, "form": latest["form"]})
            continue

        mission, f1, theme_shares = mission_score(lines, client, tagger, model["mission"])
        geo, f2, geo_detail = geography_score(lines, client, model["geography"])
        size, f3, size_detail = size_score(lines, client, model["size"])
        peer, peers_hit = peer_score(lines, client, model["peer"])
        openness, f4, new_rate = openness_score(lines, latest, model["openness"])
        activity, _ = activity_score(dict(giving), latest_year, model["activity"])
        if hf.get("drop_oversized") and "oversized_hand_review" in f3:
            dropped.append({"ein": ein, "name": name, "reason": "oversized grants", "form": latest["form"]})
            continue

        comps = {"mission": mission, "geography": geo, "size": size, "peer": peer,
                 "openness": openness, "activity": activity}
        score = sum(w[k] * v for k, v in comps.items())
        flags = f1 + f2 + f3 + f4
        if client.get("flag_lobbying"):
            restr = (latest.get("restrictions_text") or "").lower()
            if any(k in restr for k in model.get("lobbying_keywords", [])):
                flags.append("restricts_lobbying")
        if latest["form"] == "990":
            flags.append("public_charity_schedule_I")

        ny_lines = [g for g in lines if (g["state"] or "").upper() in client["primary_states"]]
        top_ny = sorted(ny_lines, key=lambda g: -g["amount"])[:5]
        prospects.append({
            "ein": ein, "name": name, "form": latest["form"], "city": latest["city"], "state": latest["state"],
            "score": round(score, 1), "tier": tier_for(score, model["tiers"]),
            **{k: round(v, 3) for k, v in comps.items()},
            "avg_annual_giving": avg_giving, "latest_year": latest["tax_year"],
            "median_grant": size_detail["median_grant"],
            "median_grantee_revenue": size_detail["median_grantee_revenue"],
            "primary_state_share": geo_detail.get("primary_state_share"),
            "focus_county_share": geo_detail.get("focus_county_share"),
            "rural_share": geo_detail.get("rural_share"),
            "new_grantee_rate": new_rate,
            "n_grants": len(lines), "n_primary_state_grants": len(ny_lines),
            "top_themes": ", ".join(t for t, _ in sorted(theme_shares.items(), key=lambda kv: -kv[1])[:3]),
            "peers_funded": "; ".join(peers_hit),
            "top_primary_state_recipients": "; ".join(
                f"{g['recipient_name']} (${g['amount']:,.0f}, {g['tax_year']})" for g in top_ny),
            "application": latest.get("application_text") or "",
            "restrictions": latest.get("restrictions_text") or "",
            "preselected_only": bool(latest.get("preselected_only")),
            "flags": ", ".join(dict.fromkeys(flags)),
        })

    prospects.sort(key=lambda p: -p["score"])
    for i, p in enumerate(prospects, 1):
        p["rank"] = i
    result = {
        "prospects": prospects, "dropped": dropped,
        "validation": validate(client, prospects, dropped),
        "grantee_leads": grantee_leads(grants, client, tagger) if client["mode"] == "bd" else [],
        "meta": {"years": years, "n_funders": len(filings), "n_grants": len(grants)},
    }
    return result


def validate(client, prospects, dropped, threshold=95):
    """Where did each validation seed land? Seeds in Tier C or lower mean the
    model is wrong, not the funder. The name threshold is strict on purpose:
    "Community Foundation of the Southern Finger Lakes" must not match
    "Finger Lakes Community Foundation"."""
    out = []
    for seed in client["validation_seeds"]:
        s = normalize(seed)
        hit = max(prospects, key=lambda p: similarity(s, normalize(p["name"])), default=None)
        if hit and similarity(s, normalize(hit["name"])) >= threshold:
            ok = hit["tier"] in ("A", "B")
            out.append({"seed": seed, "found": "Y", "matched_name": hit["name"], "form": hit["form"],
                        "rank": hit["rank"], "tier": hit["tier"], "score": hit["score"],
                        "status": "OK" if ok else "CHECK MODEL"})
            continue
        d = max(dropped, key=lambda p: similarity(s, normalize(p["name"] or "")), default=None)
        if d and similarity(s, normalize(d["name"] or "")) >= threshold:
            out.append({"seed": seed, "found": "Y", "matched_name": d["name"], "form": d["form"], "rank": None,
                        "tier": "dropped", "score": None, "status": f"DROPPED: {d['reason']}"})
        else:
            out.append({"seed": seed, "found": "N", "matched_name": None, "form": None, "rank": None,
                        "tier": None, "score": None, "status": "not in data yet"})
    return out


def grantee_leads(grants, client, tagger) -> list[dict]:
    """bd mode: upstate NY nonprofits in the client's sectors that already win
    foundation grants. INTERNAL sales material."""
    rules = client.get("grantee_leads") or {}
    if not rules:
        return []
    by_org = defaultdict(list)
    for g in grants:
        if g["bmf_ein"]:
            by_org[g["bmf_ein"]].append(g)
    leads = []
    for ein, gs in by_org.items():
        g0 = gs[0]
        rev = g0["recipient_revenue"]
        if rev is None or not (rules["min_revenue"] <= rev <= rules["max_revenue"]):
            continue
        if len(gs) < rules["min_foundation_grants"]:
            continue
        county = g0["bmf_county"] or g0["county_name"]
        if rules.get("region") == "upstate" and not is_upstate_ny(g0["state"], county):
            continue
        themes = set()
        for g in gs:
            themes |= tagger.tag(g["purpose"], g["recipient_name"], g["ntee"])
        themes &= set(rules.get("themes", []))
        if not themes:
            continue
        in_focus = clean_county(county) in client["focus_counties"]
        lead_name = g0["bmf_name"] or g0["recipient_name"]
        known = any(similarity(normalize(lead_name), normalize(p)) >= 90 for p in client["peers"])
        leads.append({
            "ein": ein, "name": lead_name, "city": g0["city"], "on_peer_list": "Y" if known else "",
            "county": county, "ntee": g0["ntee"], "revenue": rev, "n_grants": len(gs),
            "total_awarded": sum(g["amount"] for g in gs),
            "funders": len({g["funder_ein"] for g in gs}),
            "themes": ", ".join(sorted(themes)), "focus_region": "Y" if in_focus else "",
        })
    # new names first, then the focus region, then by dollars won
    leads.sort(key=lambda r: (r["on_peer_list"] == "Y", r["focus_region"] != "Y", -r["total_awarded"]))
    return leads
