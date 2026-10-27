"""SQLite storage. One database file holds filings, grants and reference data.

Never commit the database to git (see .gitignore).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    object_id        TEXT PRIMARY KEY,
    ein              TEXT NOT NULL,
    name             TEXT,
    form             TEXT,            -- 990PF or 990
    tax_year         INTEGER,
    tax_period_end   TEXT,
    state            TEXT,
    city             TEXT,
    zip              TEXT,
    amended          INTEGER DEFAULT 0,
    preselected_only INTEGER DEFAULT 0,
    application_text TEXT,
    restrictions_text TEXT,
    total_grants_paid REAL,
    total_assets     REAL,
    source           TEXT
);
CREATE INDEX IF NOT EXISTS ix_filings_ein_year ON filings(ein, tax_year);

CREATE TABLE IF NOT EXISTS grants (
    grant_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id       TEXT NOT NULL REFERENCES filings(object_id) ON DELETE CASCADE,
    funder_ein      TEXT NOT NULL,
    tax_year        INTEGER,
    recipient_name  TEXT,
    recipient_ein   TEXT,             -- Schedule I only; 990-PF lines have none
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    purpose         TEXT,
    amount          REAL,
    recipient_status TEXT,
    source_form     TEXT
);
CREATE INDEX IF NOT EXISTS ix_grants_funder ON grants(funder_ein, tax_year);

CREATE TABLE IF NOT EXISTS bmf (
    ein          TEXT PRIMARY KEY,
    name         TEXT,
    norm_name    TEXT,
    city         TEXT,
    state        TEXT,
    zip          TEXT,
    ntee         TEXT,
    subsection   TEXT,
    foundation   TEXT,
    revenue      REAL,
    assets       REAL
);
CREATE INDEX IF NOT EXISTS ix_bmf_state_norm ON bmf(state, norm_name);

CREATE TABLE IF NOT EXISTS zip_geo (
    zip          TEXT PRIMARY KEY,
    county_fips  TEXT,
    county_name  TEXT,
    state        TEXT,
    ruca         REAL
);

CREATE TABLE IF NOT EXISTS matches (
    grant_id   INTEGER PRIMARY KEY REFERENCES grants(grant_id) ON DELETE CASCADE,
    bmf_ein    TEXT,
    score      REAL,
    method     TEXT                  -- ein, exact, fuzzy
);

CREATE TABLE IF NOT EXISTS parse_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source    TEXT,
    object_id TEXT,
    level     TEXT,
    message   TEXT,
    logged_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def log(con: sqlite3.Connection, source: str, object_id: str | None, level: str, message: str) -> None:
    con.execute("INSERT INTO parse_log(source, object_id, level, message) VALUES (?,?,?,?)",
                (source, object_id, level, message))


def save_filing(con: sqlite3.Connection, filing: dict, grants: list[dict]) -> str:
    """Store one parsed return. Keeps only the latest return per (EIN, tax year),
    so an amended return replaces the original. Returns 'saved' or 'skipped'."""
    existing = con.execute(
        "SELECT object_id FROM filings WHERE ein=? AND tax_year=? AND form=?",
        (filing["ein"], filing["tax_year"], filing["form"])).fetchall()
    for row in existing:
        # IRS object IDs increase over time, so a larger ID is a later submission.
        if str(row["object_id"]) >= str(filing["object_id"]):
            return "skipped"
        con.execute("DELETE FROM filings WHERE object_id=?", (row["object_id"],))
    cols = ["object_id", "ein", "name", "form", "tax_year", "tax_period_end", "state", "city", "zip",
            "amended", "preselected_only", "application_text", "restrictions_text",
            "total_grants_paid", "total_assets", "source"]
    con.execute(f"INSERT OR REPLACE INTO filings({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                [filing.get(c) for c in cols])
    gcols = ["object_id", "funder_ein", "tax_year", "recipient_name", "recipient_ein", "city", "state",
             "zip", "purpose", "amount", "recipient_status", "source_form"]
    con.executemany(
        f"INSERT INTO grants({','.join(gcols)}) VALUES ({','.join('?' * len(gcols))})",
        [[g.get(c) for c in gcols] for g in grants])
    return "saved"
