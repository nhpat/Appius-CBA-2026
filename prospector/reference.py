"""Load reference files: IRS Business Master File, Census ZIP-to-county, USDA RUCA.

BMF:    https://www.irs.gov/pub/irs-soi/eo_{state}.csv  (one CSV per state)
Census: https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt
RUCA:   https://www.ers.usda.gov/data-products/rural-urban-commuting-area-codes/
        Download the ZIP-code file by hand (xlsx or csv) into data/reference/.
"""
from __future__ import annotations

import csv
from pathlib import Path

from prospector.names import normalize


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def load_bmf(con, paths: list[Path]) -> int:
    n = 0
    for path in paths:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            rows = []
            for r in csv.DictReader(f):
                rows.append((
                    r["EIN"].strip(), r.get("NAME"), normalize(r.get("NAME")), r.get("CITY"),
                    (r.get("STATE") or "").upper(), (r.get("ZIP") or "")[:5], (r.get("NTEE_CD") or "").strip(),
                    r.get("SUBSECTION"), r.get("FOUNDATION"), _num(r.get("REVENUE_AMT")), _num(r.get("ASSET_AMT")),
                ))
            con.executemany("INSERT OR REPLACE INTO bmf VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
            n += len(rows)
    con.commit()
    return n


def load_zcta_county(con, path: Path) -> int:
    """Census 2020 ZCTA-to-county relationship file (pipe-delimited).
    A ZIP that crosses county lines is assigned the county holding the most land."""
    best: dict[str, tuple[float, str, str]] = {}
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f, delimiter="|"):
            z = (r.get("GEOID_ZCTA5_20") or "").strip()
            fips = (r.get("GEOID_COUNTY_20") or "").strip()
            if not z or not fips:
                continue
            area = _num(r.get("AREALAND_PART")) or 0.0
            if z not in best or area > best[z][0]:
                best[z] = (area, fips, r.get("NAMELSAD_COUNTY_20") or "")
    rows = [(z, fips, name, STATE_FIPS.get(fips[:2])) for z, (_, fips, name) in best.items()]
    con.executemany(
        "INSERT INTO zip_geo(zip, county_fips, county_name, state) VALUES (?,?,?,?) "
        "ON CONFLICT(zip) DO UPDATE SET county_fips=excluded.county_fips, "
        "county_name=excluded.county_name, state=excluded.state", rows)
    con.commit()
    return len(rows)


def load_ruca(con, path: Path) -> int:
    """USDA ERS RUCA by ZIP. Accepts .csv or .xlsx. Finds the ZIP column and the
    primary RUCA column by header name, because column names change by release."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        rows_iter = ws.iter_rows(values_only=True)
        header = None
        for row in rows_iter:  # skip title rows until a header with ZIP in it
            if row and any(isinstance(c, str) and "ZIP" in c.upper() for c in row):
                header = [str(c or "").strip() for c in row]
                break
        data = [dict(zip(header, row)) for row in rows_iter] if header else []
    else:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            data = list(reader)
    zip_col = next((h for h in header if h.upper().replace(" ", "_") in ("ZIP_CODE", "ZIPCODE", "ZIP")), None) \
        or next((h for h in header if "ZIP" in h.upper() and "TYPE" not in h.upper()), None)
    ruca_col = next((h for h in header if h.upper().replace(" ", "") in ("RUCA1", "PRIMARYRUCA", "PRIMARY_RUCA")),
                    None) or next((h for h in header if h.upper().startswith("RUCA")), None)
    if not zip_col or not ruca_col:
        raise ValueError(f"Can't find ZIP and RUCA columns in {path.name}: {header}")
    rows = []
    for r in data:
        z, v = r.get(zip_col), _num(r.get(ruca_col))
        if z is None or v is None:
            continue
        rows.append((str(z).strip().split(".")[0].zfill(5), v))
    con.executemany("INSERT INTO zip_geo(zip, ruca) VALUES (?,?) ON CONFLICT(zip) DO UPDATE SET ruca=excluded.ruca",
                    rows)
    con.commit()
    return len(rows)


STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "72": "PR",
}
