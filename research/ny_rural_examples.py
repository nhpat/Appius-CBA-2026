
import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

# Load the existing ZIP comparison
comparison = {}

with open(
    "research/hrsa_ruca_comparison.csv",
    newline="",
    encoding="utf-8-sig"
) as f:
    for row in csv.DictReader(f):
        comparison[row["zip"]] = row

# Connect to the database
conn = sqlite3.connect("data/prospector.db")
conn.row_factory = sqlite3.Row

# Fetch grants and foundation names
grants = conn.execute("""
    SELECT
        g.grant_id,
        g.funder_ein,
        COALESCE(
            (SELECT f.name
             FROM filings f
             WHERE f.ein = g.funder_ein
             AND f.name IS NOT NULL
             LIMIT 1),
            'Unknown foundation'
        ) AS funder_name,
        g.recipient_name,
        g.zip,
        g.amount
    FROM grants g
""").fetchall()

# Build grant summaries by ZIP
grants_by_zip = defaultdict(list)

for grant in grants:
    raw_zip = str(grant["zip"] or "").strip()
    zip_code = raw_zip.split("-")[0].zfill(5)

    if zip_code in comparison:
        grants_by_zip[zip_code].append(grant)

# Find New York ZIPs that change
changed_ny = []

for zip_code, row in comparison.items():
    if (
        row["state"] == "NY"
        and row["change"] in (
            "Urban to Rural",
            "Rural to Urban"
        )
    ):
        zip_grants = grants_by_zip[zip_code]

        changed_ny.append({
            **row,
            "grant_count": len(zip_grants),
            "grant_dollars": sum(
                g["amount"] or 0 for g in zip_grants
            )
        })

# Sort by amount of grantmaking affected
changed_ny.sort(
    key=lambda x: x["grant_dollars"],
    reverse=True
)

print("\n===== NEW YORK RURAL CLASSIFICATION =====")
print(f"NY ZIPs changing status: {len(changed_ny)}")

for category in ("Urban to Rural", "Rural to Urban"):
    category_rows = [
        r for r in changed_ny
        if r["change"] == category
    ]

    print(f"\n{category}: {len(category_rows)} ZIPs")
    print("Top 10 by associated grant dollars:")

    for r in category_rows[:10]:
        print(
            f"{r['zip']} | "
            f"{r['county']} | "
            f"RUCA {r['ruca']} | "
            f"{r['grant_count']} grants | "
            f"${r['grant_dollars']:,.2f}"
        )

        # Show two actual grant records
        for g in grants_by_zip[r["zip"]][:2]:
            print(
                f"  Funder: {g['funder_name']} | "
                f"Recipient: {g['recipient_name']} | "
                f"Amount: ${g['amount'] or 0:,.2f}"
            )

# Export all changed NY ZIPs
output = Path("research/ny_rural_changes.csv")

with output.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "zip", "county", "state", "ruca",
            "current_rural", "hrsa_rural",
            "change", "grant_count", "grant_dollars"
        ]
    )
    writer.writeheader()
    writer.writerows(changed_ny)

print(f"\nSaved: {output}")

conn.close()
