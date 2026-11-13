
import sqlite3
import csv
from collections import Counter, defaultdict
from pathlib import Path
from openpyxl import load_workbook

# --------------------------------------------------
# 1. File locations
# --------------------------------------------------

DB_PATH = Path("data/prospector.db")
HRSA_PATH = Path(
    "research/rural-zip-code-approximations.xlsx"
)
OUTPUT_PATH = Path("research/hrsa_ruca_comparison.csv")

# --------------------------------------------------
# 2. Helper: preserve 5-digit ZIP codes
# --------------------------------------------------

def clean_zip(value):
    if value is None:
        return None

    value = str(value).strip()

    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]

    # Handle ZIP+4
    value = value.split("-")[0]

    if value.isdigit() and 1 <= len(value) <= 5:
        return value.zfill(5)

    return None

# --------------------------------------------------
# 3. Load HRSA rural ZIP classifications
# --------------------------------------------------

print("Loading HRSA workbook...")

wb = load_workbook(
    HRSA_PATH,
    read_only=True,
    data_only=True
)

ws = wb["ZIP Code Approximations"]

headers = [
    str(cell.value).strip() if cell.value is not None else ""
    for cell in next(ws.iter_rows(max_row=1))
]

zip_col = headers.index("ZIP_CODE")
rural_col = headers.index("FORHP_Rural_approximation")

hrsa = {}

for row in ws.iter_rows(min_row=2, values_only=True):
    zip_code = clean_zip(row[zip_col])

    if zip_code is None:
        continue

    raw_status = row[rural_col]
    status = str(raw_status).strip().lower()

    if status == "yes":
        rural = "Yes"
    elif status == "no":
        rural = "No"
    else:
        rural = "Unknown"

    if zip_code in hrsa and hrsa[zip_code] != rural:
        raise ValueError(
            f"Conflicting HRSA classifications for {zip_code}"
        )

    hrsa[zip_code] = rural

wb.close()

print(f"Loaded {len(hrsa):,} HRSA ZIP codes.")

# --------------------------------------------------
# 4. Load current RUCA classifications
# --------------------------------------------------

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT zip, county_name, state, ruca
    FROM zip_geo
    ORDER BY zip
""")

comparison = {}
results = []

for zip_raw, county, state, ruca in cursor.fetchall():
    zip_code = clean_zip(zip_raw)

    if zip_code is None:
        continue

    if ruca is None:
        current = "Unknown"
    elif 4 <= ruca <= 10:
        current = "Yes"
    else:
        current = "No"

    hrsa_status = hrsa.get(zip_code, "Unknown")

    if current == "Unknown" or hrsa_status == "Unknown":
        change = "Unknown"
    elif current == hrsa_status:
        change = "No change"
    elif current == "No" and hrsa_status == "Yes":
        change = "Urban to Rural"
    else:
        change = "Rural to Urban"

    record = {
        "zip": zip_code,
        "county": county,
        "state": state,
        "ruca": ruca,
        "current_rural": current,
        "hrsa_rural": hrsa_status,
        "change": change
    }

    comparison[zip_code] = record
    results.append(record)

# --------------------------------------------------
# 5. Export the ZIP-by-ZIP comparison
# --------------------------------------------------

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_PATH.open(
    "w", newline="", encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "zip",
            "county",
            "state",
            "ruca",
            "current_rural",
            "hrsa_rural",
            "change"
        ]
    )

    writer.writeheader()
    writer.writerows(results)

# --------------------------------------------------
# 6. Count rural classifications
# --------------------------------------------------

current_counts = Counter(
    r["current_rural"] for r in results
)

hrsa_counts = Counter(
    r["hrsa_rural"] for r in results
)

change_counts = Counter(
    r["change"] for r in results
)

print("\n===== ZIP CLASSIFICATION RESULTS =====")

print(f"Total project ZIPs: {len(results):,}")
print(f"Current RUCA rural: {current_counts['Yes']:,}")
print(f"HRSA rural: {hrsa_counts['Yes']:,}")
print(f"HRSA urban: {hrsa_counts['No']:,}")
print(f"HRSA unknown: {hrsa_counts['Unknown']:,}")

print("\nCHANGES:")
for category in [
    "Urban to Rural",
    "Rural to Urban",
    "No change",
    "Unknown"
]:
    print(f"{category}: {change_counts[category]:,}")

# --------------------------------------------------
# 7. Show specific ZIP examples
# --------------------------------------------------

print("\n===== EXAMPLES: URBAN TO RURAL =====")

urban_to_rural = [
    r for r in results if r["change"] == "Urban to Rural"
]

for r in urban_to_rural[:10]:
    print(
        r["zip"],
        r["county"],
        r["state"],
        "RUCA:", r["ruca"]
    )

print("\n===== EXAMPLES: RURAL TO URBAN =====")

rural_to_urban = [
    r for r in results if r["change"] == "Rural to Urban"
]

for r in rural_to_urban[:10]:
    print(
        r["zip"],
        r["county"],
        r["state"],
        "RUCA:", r["ruca"]
    )

# --------------------------------------------------
# 8. Compare grant dollars by recipient ZIP
# --------------------------------------------------

cursor.execute("""
    SELECT grant_id, zip, amount
    FROM grants
""")

grant_summary = defaultdict(
    lambda: {"count": 0, "dollars": 0.0}
)

for grant_id, zip_raw, amount in cursor.fetchall():
    zip_code = clean_zip(zip_raw)

    if zip_code is None or zip_code not in comparison:
        category = "Missing project geography"
    else:
        category = comparison[zip_code]["change"]

    grant_summary[category]["count"] += 1
    grant_summary[category]["dollars"] += amount or 0

print("\n===== GRANT DOLLARS BY ZIP CHANGE =====")

for category in [
    "Urban to Rural",
    "Rural to Urban",
    "No change",
    "Unknown",
    "Missing project geography"
]:
    info = grant_summary[category]

    print(
        f"{category}: "
        f"{info['count']:,} grants, "
        f"${info['dollars']:,.2f}"
    )

# --------------------------------------------------
# 9. Calculate rural grant totals under each rule
# --------------------------------------------------

cursor.execute("""
    SELECT grant_id, zip, amount
    FROM grants
""")

current_dollars = 0
hrsa_dollars = 0

for grant_id, zip_raw, amount in cursor.fetchall():
    zip_code = clean_zip(zip_raw)
    record = comparison.get(zip_code)

    if record is None:
        continue

    amount = amount or 0

    if record["current_rural"] == "Yes":
        current_dollars += amount

    if record["hrsa_rural"] == "Yes":
        hrsa_dollars += amount

print("\n===== RURAL GRANT DOLLAR TOTALS =====")

print(f"Current RUCA: ${current_dollars:,.2f}")
print(f"HRSA approximation: ${hrsa_dollars:,.2f}")
print(f"Net difference: ${hrsa_dollars-current_dollars:,.2f}")

print("\nSaved comparison to:", OUTPUT_PATH)

conn.close()
