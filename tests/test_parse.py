from pathlib import Path

from prospector import db
from prospector.parse990 import parse_return

XML = Path(__file__).parent / "fixtures" / "xml"


def _parse(name_contains):
    for p in sorted(XML.glob("*.xml")):
        raw = p.read_bytes()
        if name_contains.encode() in raw:
            yield parse_return(raw, p.stem)


def test_990pf_current_schema():
    filing, grants, warnings = next(_parse("Lakeview Health Fund"))
    assert filing["form"] == "990PF" and filing["ein"] == "900000001"
    assert filing["tax_year"] == 2022 and filing["state"] == "NY"
    assert filing["application_text"].startswith("Letter of inquiry")
    assert filing["preselected_only"] == 0
    assert len(grants) == 4 and not warnings
    g = grants[0]
    assert g["recipient_name"] == "NYS Association of County Health Officials Inc"
    assert g["state"] == "NY" and g["zip"] == "12207" and g["amount"] == 150000
    assert g["recipient_ein"] is None  # 990-PF lines carry no recipient EIN


def test_990pf_old_schema_names():
    """Hudson Arts 2022 uses pre-2013 style element names."""
    olds = [r for r in _parse("Hudson Arts Foundation") if r[0]["tax_year"] == 2022]
    filing, grants, _ = olds[0]
    assert filing["form"] == "990PF" and filing["name"] == "Hudson Arts Foundation"
    assert {g["recipient_name"] for g in grants} == {"Brooklyn Arts Collective Inc",
                                                      "Manhattan Museum of Modern Craft"}
    assert grants[0]["city"] == "Brooklyn" and grants[0]["purpose"] == "Artist residencies"


def test_preselected_flag():
    filing, _, _ = next(_parse("Smith Family Foundation"))
    assert filing["preselected_only"] == 1


def test_schedule_i_has_recipient_ein():
    filing, grants, _ = next(_parse("Finger Lakes Community Foundation"))
    assert filing["form"] == "990"
    assert len(grants) == 5 and all(g["recipient_ein"] for g in grants)
    assert grants[0]["source_form"] == "990SchI"


def test_990ez_ignored():
    filing, grants, _ = next(_parse("Small Garden Club"))
    assert filing is None and grants == []


def test_bad_xml_reports_error():
    filing, grants, warnings = parse_return(b"<Return><oops>", "x")
    assert filing is None and warnings and "parse error" in warnings[0]


def test_amended_return_replaces_original(con):
    rows = con.execute("SELECT object_id FROM filings WHERE ein='900000001' AND tax_year=2024").fetchall()
    assert len(rows) == 1 and rows[0]["object_id"].endswith("999")
    n = con.execute("SELECT COUNT(*) FROM grants WHERE funder_ein='900000001' AND tax_year=2024").fetchone()[0]
    assert n == 6
    # re-ingesting the older original must not overwrite the amended return
    older = {"object_id": "202500000000000001", "ein": "900000001", "form": "990PF", "tax_year": 2024}
    assert db.save_filing(con, older, []) == "skipped"
