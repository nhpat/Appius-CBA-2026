import json
from pathlib import Path

import pytest

from prospector import db, irs, match, reference
from prospector.config import load_model

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def con(tmp_path):
    """A database loaded with the synthetic fixtures."""
    c = db.connect(tmp_path / "test.db")
    reference.load_bmf(c, [FIX / "bmf_fixture.csv"])
    reference.load_zcta_county(c, FIX / "zcta_county_fixture.txt")
    reference.load_ruca(c, FIX / "ruca_fixture.csv")
    irs.ingest_xml_files(c, sorted((FIX / "xml").glob("*.xml")))
    match.run_matching(c, load_model()["matching"]["fuzzy_threshold"])
    return c


@pytest.fixture
def grantsgov_payloads():
    return json.loads((FIX / "grantsgov_fixture.json").read_text())
