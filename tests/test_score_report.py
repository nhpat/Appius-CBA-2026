from openpyxl import load_workbook

from prospector import grantsgov, report
from prospector.config import load_client, load_model, load_taxonomy
from prospector.score import activity_score, score_client, tier_for


def _run(con, cid):
    return score_client(con, load_client(cid), load_model(), load_taxonomy())


def _by_name(result):
    return {p["name"]: p for p in result["prospects"]}


def test_weights_add_to_100():
    assert sum(load_model()["weights"].values()) == 100


def test_tiers():
    tiers = load_model()["tiers"]
    assert [tier_for(s, tiers) for s in (74, 66, 53, 38)] == ["A", "B", "C", "Watch"]


def test_workbook_sandbox_scores():
    """The four example rows on the workbook's Fit Model tab."""
    w = load_model()["weights"]
    rows = [((0.85, 0.70, 0.90, 0.50, 0.75, 0.60), 74), ((1.00, 0.30, 0.40, 0.50, 0.75, 0.90), 66),
            ((0.60, 0.90, 0.80, 0.00, 0.10, 0.40), 53), ((0.00, 0.70, 0.50, 0.00, 0.75, 0.90), 38)]
    keys = ["mission", "geography", "size", "peer", "openness", "activity"]
    for vals, expected in rows:
        assert round(sum(w[k] * v for k, v in zip(keys, vals))) == expected


def test_hard_filters(con):
    dropped = {d["name"]: d["reason"] for d in _run(con, "nyspha")["dropped"]}
    assert "Tiny Giving Fund" in dropped and "under $250,000" in dropped["Tiny Giving Fund"]
    assert "Dormant Family Foundation" in dropped and "since 2019" in dropped["Dormant Family Foundation"]


def test_size_is_not_a_hard_filter(con):
    p = _by_name(_run(con, "nyspha"))["National Health Research Trust"]
    assert p["median_grant"] > 1_000_000
    assert "oversized_hand_review" in p["flags"] and "restricts_lobbying" in p["flags"]
    assert p["tier"] in ("A", "B")    # stays on the list; a person reviews it


def test_preselected_scores_low_on_openness(con):
    p = _by_name(_run(con, "appius"))["Smith Family Foundation"]
    assert p["openness"] == 0.1 and "preselected_only" in p["flags"]


def test_rankings_make_sense(con):
    ny = _run(con, "nyspha")["prospects"]
    ap = _run(con, "appius")["prospects"]
    assert ny[0]["name"] == "Lakeview Health Fund"
    assert ap[0]["name"] == "Finger Lakes Community Foundation Inc"
    assert "Common Ground Health" in ny[0]["peers_funded"]


def test_missing_data_is_neutral_not_zero():
    # one year of data: trend is neutral (0.5), not zero
    cfg = load_model()["activity"]
    one_year, _ = activity_score({2024: 1_000_000}, 2024, cfg)
    assert one_year > cfg["parts"]["level"] * 0.7


def test_grantee_leads_internal_and_upstate(con):
    leads = _run(con, "appius")["grantee_leads"]
    names = {l["name"] for l in leads}
    assert "SOUTHERN TIER RECOVERY CENTER INC" in names
    assert "BROOKLYN ARTS COLLECTIVE INC" not in names         # NYC and wrong sector
    assert all(250_000 <= l["revenue"] <= 10_000_000 for l in leads)
    assert not _run(con, "nyspha")["grantee_leads"]           # seek mode has no leads


def test_validation_seed_not_fooled_by_similar_name(con):
    v = {x["seed"]: x for x in _run(con, "appius")["validation"]}
    assert v["Community Foundation of the Southern Finger Lakes"]["found"] == "N"


def test_grantsgov_dedupes(grantsgov_payloads):
    hits = grantsgov.search_client(load_client("nyspha"), offline_payloads=grantsgov_payloads)
    numbers = [h["number"] for h in hits]
    assert len(numbers) == len(set(numbers)) == 3


def test_report_writes_excel(con, tmp_path, grantsgov_payloads):
    client = load_client("appius")
    result = score_client(con, client, load_model(), load_taxonomy())
    fed = grantsgov.search_client(client, offline_payloads=grantsgov_payloads)
    path = report.write_report(client, result, fed, tmp_path)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Read Me", "Prospects", "Validation", "Dropped", "Federal",
                             "Grantee Leads (INTERNAL)"]
    assert wb["Prospects"]["D2"].value == "Finger Lakes Community Foundation Inc"
