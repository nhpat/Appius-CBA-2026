"""Write one formatted Excel file per client."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TIER_FILL = {"A": "C6EFCE", "B": "FFEB9C", "C": "FCE4D6", "Watch": "EDEDED"}

PROSPECT_COLS = [
    ("rank", "Rank", 6), ("tier", "Tier", 6), ("score", "Score", 7), ("name", "Foundation", 38),
    ("ein", "EIN", 11), ("form", "Form", 7), ("city", "City", 14), ("state", "State", 6),
    ("mission", "Mission (0-1)", 9), ("geography", "Geography (0-1)", 9), ("size", "Size (0-1)", 7),
    ("peer", "Peer (0-1)", 7), ("openness", "Openness (0-1)", 9), ("activity", "Activity (0-1)", 8),
    ("avg_annual_giving", "Avg annual giving", 14), ("median_grant", "Median grant", 12),
    ("median_grantee_revenue", "Median grantee revenue", 14), ("primary_state_share", "Share to primary state", 10),
    ("focus_county_share", "Share to focus counties", 10), ("rural_share", "Share to rural ZIPs", 10),
    ("n_grants", "# grants", 8), ("n_primary_state_grants", "# in primary state", 9),
    ("top_themes", "Top themes", 30), ("peers_funded", "Peers funded", 30),
    ("top_primary_state_recipients", "Top in-state recipients", 60), ("application", "How to apply", 50),
    ("restrictions", "Restrictions", 40), ("latest_year", "Latest tax year", 9), ("flags", "Flags to check", 34),
]
MONEY = {"avg_annual_giving", "median_grant", "median_grantee_revenue", "revenue", "total_awarded"}
PCT = {"primary_state_share", "focus_county_share", "rural_share"}


def _sheet(ws, cols, rows, tier_col=None):
    for j, (_, label, width) in enumerate(cols, 1):
        c = ws.cell(row=1, column=j, value=label)
        c.fill, c.font = HEADER_FILL, HEADER_FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(j)].width = width
    for i, r in enumerate(rows, 2):
        for j, (key, _, _) in enumerate(cols, 1):
            v = r.get(key)
            c = ws.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if key in MONEY:
                c.number_format = '"$"#,##0'
            elif key in PCT:
                c.number_format = "0%"
            elif isinstance(v, float):
                c.number_format = "0.00"
        if tier_col and r.get(tier_col) in TIER_FILL:
            col = [k for k, *_ in cols].index(tier_col) + 1
            ws.cell(row=i, column=col).fill = PatternFill("solid", fgColor=TIER_FILL[r[tier_col]])
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(rows) + 1}"


def write_report(client: dict, result: dict, federal: list[dict], out_dir: Path,
                 match_stats: dict | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    readme = wb.active
    readme.title = "Read Me"
    years = result["meta"].get("years", [])
    tiers = {t: sum(1 for p in result["prospects"] if p["tier"] == t) for t in ("A", "B", "C", "Watch")}
    lines = [
        (f"Foundation prospects: {client['name']}", True),
        (f"Built {date.today().isoformat()} by foundation-prospector. Tax years {years[0]}-{years[-1]}."
         if years else "No data loaded.", False),
        ("", False),
        ("How to read this", True),
        ("Score is 0 to 100: mission 30, geography 20, size 15, peer 15, openness 10, activity 10.", False),
        ("Tier A (70+) pursue now. B (55-69) research further. C (40-54) keep on file. Watch (under 40).", False),
        ("Scores rank prospects for human review. They are NOT a recommendation to apply.", False),
        ("Check every Tier A funder's CURRENT guidelines before anyone acts on it.", False),
        ("Flags mark gaps or traps a person should check. Missing data gets a neutral value plus a flag, never a zero.",
         False),
        ("IRS data lags a year or more. Scores describe patterns over several years, not last month.", False),
        ("", False),
        ("This run", True),
        (f"Funders scored: {len(result['prospects'])}  (A {tiers['A']}, B {tiers['B']}, C {tiers['C']}, "
         f"Watch {tiers['Watch']}).  Dropped by hard filters: {len(result['dropped'])}.", False),
    ]
    if match_stats and match_stats.get("match_rate") is not None:
        lines.append((f"Recipient match rate ({match_stats['state']} grant dollars matched to the IRS BMF): "
                      f"{match_stats['match_rate']:.0%} (target 60%+).", False))
    if client["mode"] == "bd":
        lines += [("", False), ("Business development mode", True),
                  ("Appius is a for-profit, so this file has funders of Appius's market, not funders for Appius. "
                   "Use it to advise clients and build collaborative bids with a nonprofit lead or fiscal sponsor.",
                   False),
                  ("The Grantee Leads tab is INTERNAL sales material. Do not share it outside Appius.", False)]
    if client["id"] == "nyspha":
        lines += [("", False), ("Handling", True),
                  ("NYSPHA outputs go to Adam only. The team does not contact NYSPHA staff.", False)]
    lines += [("", False), ("Tabs", True), ("Prospects: ranked funders. Validation: where known-good funders landed. "
                                              "Dropped: funders removed by hard filters and why. Federal: Grants.gov "
                                              "matches. NY State opportunities come from SFS email alerts "
                                              "(Gmail label 'Grant Alerts/NYS SFS').", False)]
    for i, (t, bold) in enumerate(lines, 1):
        c = readme.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold, size=14 if i == 1 else 11)
        c.alignment = Alignment(wrap_text=True)
    readme.column_dimensions["A"].width = 110

    _sheet(wb.create_sheet("Prospects"), PROSPECT_COLS, result["prospects"], tier_col="tier")
    _sheet(wb.create_sheet("Validation"),
           [("seed", "Validation seed", 40), ("found", "Found?", 7), ("matched_name", "Matched as", 38),
            ("form", "Form", 7), ("rank", "Rank", 6), ("tier", "Tier", 8), ("score", "Score", 7),
            ("status", "Status", 34)], result["validation"])
    _sheet(wb.create_sheet("Dropped"),
           [("name", "Foundation", 40), ("ein", "EIN", 11), ("form", "Form", 7), ("reason", "Why dropped", 50)],
           result["dropped"])
    _sheet(wb.create_sheet("Federal"),
           [("title", "Title", 60), ("number", "Number", 18), ("agency", "Agency", 24), ("status", "Status", 10),
            ("open_date", "Opens", 11), ("close_date", "Closes", 11), ("alns", "ALN", 12),
            ("found_by", "Found by", 30), ("link", "Link", 50)], federal)
    if client["mode"] == "bd":
        ws = wb.create_sheet("Grantee Leads (INTERNAL)")
        _sheet(ws, [("name", "Organization", 40), ("on_peer_list", "Already on peer list (client/partner)?", 12),
                    ("ein", "EIN", 11), ("city", "City", 14),
                    ("county", "County", 16), ("focus_region", "WNY/FL?", 8), ("ntee", "NTEE", 7),
                    ("revenue", "Revenue", 13), ("n_grants", "# foundation grants", 10),
                    ("funders", "# funders", 9), ("total_awarded", "Total awarded", 13),
                    ("themes", "Themes", 36)], result["grantee_leads"])
        ws.sheet_properties.tabColor = "C00000"

    path = out_dir / f"{client['id']}_prospects_{date.today().isoformat()}.xlsx"
    wb.save(path)
    return path
