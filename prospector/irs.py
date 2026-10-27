"""Download and ingest IRS bulk e-file data.

Index:   https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/index_{YEAR}.csv
Zips:    https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/<name>.zip
         (names change; check https://www.irs.gov/charities-non-profits/form-990-series-downloads)

The {YEAR} is the IRS PROCESSING year, not the tax year. A 2025 zip holds
returns for tax years 2023, 2024 and some 2025.
"""
from __future__ import annotations

import csv
import time
import zipfile
from pathlib import Path

from prospector import USER_AGENT, db

BASE = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/"


def download(url: str, dest_dir: Path, pause: float = 1.0) -> Path:
    """Download once and cache. Large files stream to disk."""
    import requests

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / url.rsplit("/", 1)[-1]
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    time.sleep(pause)
    return dest


def index_url(year: int) -> str:
    return BASE.format(year=year) + f"index_{year}.csv"


def summarize_index(path: Path) -> dict:
    """Count returns by type in a yearly index CSV."""
    counts: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            rt = (row.get("RETURN_TYPE") or "").strip()
            counts[rt] = counts.get(rt, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def index_object_ids(path: Path, return_types=("990PF",)) -> set[str]:
    ids = set()
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if (row.get("RETURN_TYPE") or "").strip() in return_types:
                ids.add(row["OBJECT_ID"].strip())
    return ids


def schedule_i_filers(con) -> set[str] | None:
    """EINs whose Form 990 we parse for Schedule I: philanthropy orgs (NTEE T)
    in NY and neighbors. Returns None when the BMF isn't loaded (parse all)."""
    n = con.execute("SELECT COUNT(*) FROM bmf").fetchone()[0]
    if not n:
        return None
    rows = con.execute(
        "SELECT ein FROM bmf WHERE ntee LIKE 'T%' AND state IN ('NY','PA','NJ','CT','MA','VT')").fetchall()
    return {r["ein"] for r in rows}


def ingest_zip(con, zip_path: Path, limit: int | None = None) -> dict:
    """Parse every 990-PF (and qualifying 990 with Schedule I) in one IRS zip."""
    from prospector.parse990 import parse_return

    sched_i_eins = schedule_i_filers(con)
    stats = {"files": 0, "saved": 0, "skipped": 0, "ignored": 0, "warnings": 0, "errors": 0, "grants": 0}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".xml"):
                continue
            stats["files"] += 1
            object_id = Path(info.filename).stem.replace("_public", "")
            raw = zf.read(info)
            head = raw[:6000]
            # cheap pre-check before a full parse
            is_pf = b"IRS990PF" in head or b"990PF" in head
            is_990 = b"<ReturnTypeCd>990<" in head or b"<ReturnType>990<" in head
            if not (is_pf or is_990):
                stats["ignored"] += 1
                continue
            filing, grants, warnings = parse_return(raw, object_id, source=zip_path.name)
            for w in warnings:
                db.log(con, zip_path.name, object_id, "warn", w)
                stats["warnings"] += 1
            if filing is None:
                stats["ignored" if not warnings else "errors"] += 1
                continue
            if filing["form"] == "990" and sched_i_eins is not None and filing["ein"] not in sched_i_eins:
                stats["ignored"] += 1
                continue
            result = db.save_filing(con, filing, grants)
            stats[result] += 1
            if result == "saved":
                stats["grants"] += len(grants)
            if limit and stats["saved"] >= limit:
                break
    con.commit()
    return stats


def ingest_xml_files(con, paths, source="fixtures") -> dict:
    """Ingest loose XML files (used by tests and the offline demo)."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / f"{source}.zip"
        with zipfile.ZipFile(tmp, "w") as zf:
            for p in paths:
                zf.write(p, Path(p).name)
        return ingest_zip(con, tmp)
