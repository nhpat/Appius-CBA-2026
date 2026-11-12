"""Workstream 5 (Reporting / QA): summarize a generated prospects workbook.

Usage:
    python docs/reporting_qa/inspect_reports.py outputs/nyspha_prospects_<date>.xlsx

Prints flag counts, tier colours, restricts_lobbying hits, low-mission B/C rows,
Federal tab date/link checks, Dropped reasons and (Appius) Grantee Leads.
Read-only: it never modifies the workbook or the database.
"""
import collections
import sys

from openpyxl import load_workbook


def rows_of(ws):
    header = [c.value for c in ws[1]]
    return [dict(zip(header, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]


def main(path):
    wb = load_workbook(path)
    print("tabs:", wb.sheetnames)
    ws = wb["Prospects"]
    rows = rows_of(ws)
    flags = collections.Counter(f for r in rows for f in (r["Flags to check"] or "").split(", ") if f)
    print(f"prospects: {len(rows)}  tiers: {dict(collections.Counter(r['Tier'] for r in rows))}")
    print("flag counts:", dict(flags))
    fills = {}
    for r in ws.iter_rows(min_row=2):
        fills.setdefault(r[1].value, r[1].fill.fgColor.rgb)
    print("tier fills:", fills)

    print("\nrestricts_lobbying hits (check the trigger word):")
    for r in rows:
        if "restricts_lobbying" in (r["Flags to check"] or ""):
            print(f"  {r['Foundation']}: {(r['Restrictions'] or '')[:160]}")

    bc = [r for r in rows if r["Tier"] in ("B", "C")]
    low = [r for r in bc if (r["Mission (0-1)"] or 0) < 0.3]
    print(f"\nB/C rows with mission < 0.3: {len(low)} of {len(bc)}")
    for r in low[:10]:
        print(f"  {r['Rank']:>3} {r['Tier']} {r['Score']:>5} {r['Foundation']}  mission={r['Mission (0-1)']}")

    fed = rows_of(wb["Federal"])
    old = sum(1 for r in fed if r["Opens"] and int(str(r["Opens"])[-4:]) < 2024)
    print(f"\nfederal: {len(fed)} rows, statuses {dict(collections.Counter(r['Status'] for r in fed))}, "
          f"blank close date {sum(r['Closes'] is None for r in fed)}, opened before 2024 {old}, "
          f"hyperlinked: {wb['Federal']['I2'].hyperlink is not None if len(fed) else 'n/a'}")

    reasons = collections.Counter(
        "avg giving under threshold" if r["Why dropped"].startswith("average giving") else r["Why dropped"]
        for r in rows_of(wb["Dropped"]))
    print("dropped reasons:", dict(reasons))

    for v in rows_of(wb["Validation"]):
        print(f"seed: {v['Validation seed']} -> {v['Matched as']} ({v['Status']})")

    if "Grantee Leads (INTERNAL)" in wb.sheetnames:
        print("\ngrantee leads:")
        for r in rows_of(wb["Grantee Leads (INTERNAL)"]):
            print(f"  {r['Organization']}: {r['Themes']}")


if __name__ == "__main__":
    main(sys.argv[1])
