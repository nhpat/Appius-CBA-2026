
import csv
import sqlite3
from pathlib import Path
from collections import Counter

import yaml
import prospector.score as scoring

# ------------------------------------------
# 1. Load project configuration
# ------------------------------------------

def read_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

model = read_yaml("config/model.yaml")
taxonomy = read_yaml("config/taxonomy.yaml")

clients = {
    "nyspha": read_yaml("config/clients/nyspha.yaml"),
    "appius": read_yaml("config/clients/appius.yaml")
}

# ------------------------------------------
# 2. Load HRSA classifications
# ------------------------------------------

hrsa_zips = {}

with open(
    "research/hrsa_ruca_comparison.csv",
    newline="",
    encoding="utf-8-sig"
) as f:
    for row in csv.DictReader(f):
        if row["hrsa_rural"] in ("Yes", "No"):
            hrsa_zips[row["zip"]] = row["hrsa_rural"]

def clean_zip(value):
    if value is None:
        return None

    value = str(value).strip().split("-")[0]

    if value.endswith(".0"):
        value = value[:-2]

    if value.isdigit() and len(value) <= 5:
        return value.zfill(5)

    return None

# ------------------------------------------
# 3. Run the baseline model
# ------------------------------------------

conn = sqlite3.connect("data/prospector.db")
conn.row_factory = sqlite3.Row

print("Running original RUCA model...")

baseline = {}

for client_id, client in clients.items():
    baseline[client_id] = scoring.score_client(
        conn, client, model, taxonomy
    )

# ------------------------------------------
# 4. Simulate HRSA rural classification
# ------------------------------------------

original_geography_score = scoring.geography_score

def hrsa_geography_score(lines, client, cfg):
    modified_lines = []

    for grant in lines:
        grant_copy = dict(grant)
        zip_code = clean_zip(grant_copy.get("zip"))

        if zip_code in hrsa_zips:
            # Retain the scoring function's existing
            # RUCA threshold logic, using temporary
            # numeric values as HRSA rural flags.
            grant_copy["ruca"] = (
                4.0 if hrsa_zips[zip_code] == "Yes"
                else 1.0
            )
        else:
            # HRSA classification unavailable.
            grant_copy["ruca"] = None

        modified_lines.append(grant_copy)

    return original_geography_score(
        modified_lines, client, cfg
    )

scoring.geography_score = hrsa_geography_score

print("Running simulated HRSA model...")

hrsa_results = {}

try:
    for client_id, client in clients.items():
        hrsa_results[client_id] = scoring.score_client(
            conn, client, model, taxonomy
        )
finally:
    # Restore the original scoring function.
    scoring.geography_score = original_geography_score

# ------------------------------------------
# 5. Compare foundation scores
# ------------------------------------------

output = Path("research/client_rural_impact.csv")

fieldnames = [
    "client",
    "ein",
    "foundation",
    "old_score",
    "hrsa_score",
    "score_change",
    "old_geography",
    "hrsa_geography",
    "old_rural_share",
    "hrsa_rural_share",
    "old_tier",
    "hrsa_tier",
    "old_rank",
    "hrsa_rank"
]

all_rows = []

for client_id in clients:
    old_prospects = {
        p["ein"]: p
        for p in baseline[client_id]["prospects"]
    }

    new_prospects = {
        p["ein"]: p
        for p in hrsa_results[client_id]["prospects"]
    }

    rows = []

    for ein, old in old_prospects.items():
        new = new_prospects.get(ein)

        if new is None:
            continue

        row = {
            "client": client_id,
            "ein": ein,
            "foundation": old["name"],
            "old_score": old["score"],
            "hrsa_score": new["score"],
            "score_change": round(
                new["score"] - old["score"], 2
            ),
            "old_geography": old["geography"],
            "hrsa_geography": new["geography"],
            "old_rural_share": old["rural_share"],
            "hrsa_rural_share": new["rural_share"],
            "old_tier": old["tier"],
            "hrsa_tier": new["tier"],
            "old_rank": old["rank"],
            "hrsa_rank": new["rank"]
        }

        rows.append(row)
        all_rows.append(row)

    score_changed = [
        r for r in rows
        if r["score_change"] != 0
    ]

    geography_changed = [
        r for r in rows
        if r["old_geography"] != r["hrsa_geography"]
    ]

    tier_changed = [
        r for r in rows
        if r["old_tier"] != r["hrsa_tier"]
    ]

    rank_changed = [
        r for r in rows
        if r["old_rank"] != r["hrsa_rank"]
    ]

    print(f"\n===== {client_id.upper()} =====")
    print(f"Total prospects: {len(rows):,}")
    print(f"Geography scores changed: "
          f"{len(geography_changed):,}")
    print(f"Displayed total scores changed: "
          f"{len(score_changed):,}")
    print(f"Tier changes: {len(tier_changed):,}")
    print(f"Rank changes: {len(rank_changed):,}")

    print("\nLargest score changes:")

    top_changes = sorted(
        score_changed,
        key=lambda r: abs(r["score_change"]),
        reverse=True
    )

    for r in top_changes[:10]:
        print(
            f"{r['foundation']} | "
            f"{r['old_score']} -> {r['hrsa_score']} | "
            f"Tier {r['old_tier']} -> {r['hrsa_tier']}"
        )

    print("\nTier changes:")

    for r in tier_changed[:20]:
        print(
            f"{r['foundation']} | "
            f"{r['old_score']} -> {r['hrsa_score']} | "
            f"{r['old_tier']} -> {r['hrsa_tier']}"
        )

with output.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_rows)

conn.close()

print("\nSaved:", output)
print("Original project model files were not changed.")
