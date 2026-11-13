
import sqlite3
import csv
from pathlib import Path

# Connect to the shared database
conn = sqlite3.connect("data/prospector.db")
cursor = conn.cursor()

# Read the current RUCA classification
cursor.execute("""
    SELECT
        zip,
        county_fips,
        county_name,
        state,
        ruca,
        CASE
            WHEN ruca BETWEEN 4 AND 10 THEN 'Yes'
            WHEN ruca IS NULL THEN 'Unknown'
            ELSE 'No'
        END AS current_rural
    FROM zip_geo
    ORDER BY zip
""")

rows = cursor.fetchall()
headers = [column[0] for column in cursor.description]

# Save results as CSV
output = Path("research/current_rural_zips.csv")
output.parent.mkdir(exist_ok=True)

with output.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)

print(f"Exported {len(rows):,} ZIP geography records.")
print(f"Saved to: {output}")

# Count classification totals
cursor.execute("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN ruca BETWEEN 4 AND 10 THEN 1 ELSE 0 END)
            AS rural,
        SUM(CASE WHEN ruca < 4 THEN 1 ELSE 0 END)
            AS urban,
        SUM(CASE WHEN ruca IS NULL THEN 1 ELSE 0 END)
            AS unknown
    FROM zip_geo
""")

total, rural, urban, unknown = cursor.fetchone()

print("\nCURRENT RUCA CLASSIFICATION")
print(f"Total records: {total:,}")
print(f"Rural records: {rural:,}")
print(f"Urban records: {urban:,}")
print(f"Unknown RUCA: {unknown:,}")

conn.close()
