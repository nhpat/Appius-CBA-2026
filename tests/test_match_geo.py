from prospector import match
from prospector.config import county_bucket, load_client
from prospector.names import normalize, similarity


def test_normalize():
    assert normalize("The Lakeview Health Fdn., Inc.") == "lakeview health foundation"
    assert normalize("NYS Assn of County Health Officials") == normalize(
        "New York State Association of County Health Officials Inc")
    assert normalize("Southern Tier Recovery Ctr Inc") == normalize("SOUTHERN TIER RECOVERY CENTER INC")


def test_similar_names_that_are_different_orgs_stay_apart():
    a = normalize("Community Foundation of the Southern Finger Lakes")
    b = normalize("Finger Lakes Community Foundation Inc")
    assert similarity(a, b) < 95


def test_matching_methods(con):
    rows = {r["recipient_name"]: r["method"] for r in con.execute(
        "SELECT g.recipient_name, m.method FROM grants g JOIN matches m USING(grant_id)")}
    assert rows["NYS Association of County Health Officials Inc"] == "exact"
    assert rows["Healthy Capitol District Initiative"] == "fuzzy"      # typo in the filing
    assert rows["Casa-Trinity Inc"] == "ein"                           # Schedule I carries the EIN
    rate = match.match_rate(con)
    assert rate["match_rate"] >= 0.6


def test_zip_to_county_uses_largest_land_area(con):
    row = con.execute("SELECT county_name, ruca FROM zip_geo WHERE zip='14830'").fetchone()
    assert row["county_name"] == "Steuben County" and row["ruca"] == 4


def test_county_buckets():
    appius = load_client("appius")
    assert county_bucket(appius, "NY", "Steuben County") == "focus"
    assert county_bucket(appius, "NY", "Franklin County") == "secondary"   # upstate, not WNY/FL
    assert county_bucket(appius, "NY", "Kings County") is None             # NYC
    assert county_bucket(appius, "PA", "Erie County") is None              # wrong state
    nyspha = load_client("nyspha")
    assert county_bucket(nyspha, "NY", "Steuben County") is None           # statewide client
