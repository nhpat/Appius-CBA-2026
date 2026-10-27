"""Download reference files into data/reference/.

  IRS Exempt Organizations Business Master File for NY and neighboring states
  Census 2020 ZCTA-to-county relationship file

The USDA ERS RUCA ZIP-code file must be downloaded BY HAND from
https://www.ers.usda.gov/data-products/rural-urban-commuting-area-codes/
and saved in data/reference/ (any file name containing "RUCA").

Then run:  python -m prospector load-reference
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prospector.irs import download  # noqa: E402

REF = Path(__file__).resolve().parent.parent / "data" / "reference"
STATES = ["ny", "pa", "nj", "ct", "ma", "vt"]
URLS = [f"https://www.irs.gov/pub/irs-soi/eo_{s}.csv" for s in STATES] + [
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
]

if __name__ == "__main__":
    for url in URLS:
        try:
            print("ok  ", download(url, REF))
        except Exception as exc:
            print("FAIL", url, exc)
    print("\nNow download the USDA RUCA ZIP-code file by hand into", REF)
