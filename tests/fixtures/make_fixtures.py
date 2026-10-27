"""Generate the SYNTHETIC test fixtures. Every organization, EIN and dollar
figure here is made up. Re-run after changing:  python tests/fixtures/make_fixtures.py

What the fixtures are built to exercise:
  Lakeview Health Fund        strong NY public health funder; has an AMENDED 2024 return
  National Health Research  big national grants (size not a hard filter); restricts lobbying
  Smith Family Foundation     preselected-only local funder (openness 0.1)
  Hudson Arts Foundation      NYC arts funder (should land in Watch); 2022 return uses OLD element names
  Tiny Giving Fund            under $250K a year (dropped by hard filter)
  Finger Lakes Community Fdn  public charity: Form 990 + Schedule I with recipient EINs
  Dormant Family Foundation   last filed 2019 (dropped by hard filter)
  A 990-EZ return             ignored by the parser
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
XML_DIR = HERE / "xml"
NS = "http://www.irs.gov/efile"

# zip: (city, state, county, county_fips, ruca)
ZIPS = {
    "14830": ("Corning", "NY", "Steuben County", "36101", 4),
    "14810": ("Bath", "NY", "Steuben County", "36101", 7),
    "14901": ("Elmira", "NY", "Chemung County", "36015", 1),
    "14850": ("Ithaca", "NY", "Tompkins County", "36109", 4),
    "12207": ("Albany", "NY", "Albany County", "36001", 1),
    "14607": ("Rochester", "NY", "Monroe County", "36055", 1),
    "14203": ("Buffalo", "NY", "Erie County", "36029", 1),
    "12983": ("Saranac Lake", "NY", "Franklin County", "36033", 7),
    "10001": ("New York", "NY", "New York County", "36061", 1),
    "11201": ("Brooklyn", "NY", "Kings County", "36047", 1),
    "19103": ("Philadelphia", "PA", "Philadelphia County", "42101", 1),
    "02108": ("Boston", "MA", "Suffolk County", "25025", 1),
    "20001": ("Washington", "DC", "District of Columbia", "11001", 1),
    "94103": ("San Francisco", "CA", "San Francisco County", "06075", 1),
}

# ein: (BMF name, zip, ntee, revenue, subsection, foundation code)
ORGS = {
    "910000001": ("NEW YORK STATE ASSOCIATION OF COUNTY HEALTH OFFICIALS INC", "12207", "E70", 3_200_000, "03", "15"),
    "910000002": ("COMMON GROUND HEALTH", "14607", "E70", 6_500_000, "03", "15"),
    "910000003": ("STEUBEN RURAL HEALTH NETWORK INC", "14810", "E21", 1_200_000, "03", "15"),
    "910000004": ("ADIRONDACK HEALTH INSTITUTE INC", "12983", "E30", 5_000_000, "03", "15"),
    "910000005": ("HEALTHY CAPITAL DISTRICT INITIATIVE INC", "12207", "E70", 900_000, "03", "15"),
    "910000006": ("CASA-TRINITY INC", "14901", "F20", 6_000_000, "03", "15"),
    "910000007": ("INSTITUTE FOR HUMAN SERVICES INC", "14810", "P20", 4_000_000, "03", "15"),
    "910000008": ("SOUTHERN TIER RECOVERY CENTER INC", "14830", "F20", 800_000, "03", "15"),
    "910000009": ("FINGER LAKES FARM STRESS COALITION", "14850", "K20", 400_000, "03", "15"),
    "910000010": ("MENTAL HEALTH ASSOCIATION IN TOMPKINS COUNTY", "14850", "F30", 2_500_000, "03", "15"),
    "910000011": ("BROOKLYN ARTS COLLECTIVE INC", "11201", "A20", 2_000_000, "03", "15"),
    "910000012": ("MANHATTAN MUSEUM OF MODERN CRAFT", "10001", "A51", 30_000_000, "03", "15"),
    "910000013": ("UNIVERSITY HOSPITAL SYSTEM", "94103", "E22", 900_000_000, "03", "15"),
    "910000014": ("PHILADELPHIA HEALTH RESEARCH INSTITUTE", "19103", "H01", 40_000_000, "03", "15"),
    "910000015": ("AMERICAN PUBLIC HEALTH ASSOCIATION", "20001", "E70", 30_000_000, "03", "15"),
    "910000016": ("ROCHESTER YOUTH SERVICES INC", "14607", "P30", 3_000_000, "03", "15"),
    "910000017": ("PACIFIC HEALTH POLICY INSTITUTE", "94103", "E70", 25_000_000, "03", "15"),
    # funders that appear in the BMF (Schedule I filter needs the community foundation's NTEE T code)
    "900000006": ("FINGER LAKES COMMUNITY FOUNDATION INC", "14901", "T31", 12_000_000, "03", "15"),
    "900000001": ("LAKEVIEW HEALTH FUND", "14607", "T20", 3_000_000, "03", "04"),
}


def addr(z, tag="RecipientUSAddress", old=False):
    city, st, *_ = ZIPS[z]
    if old:
        return (f"<{tag}><AddressLine1>1 Main St</AddressLine1><City>{escape(city)}</City>"
                f"<State>{st}</State><ZIPCode>{z}</ZIPCode></{tag}>")
    return (f"<{tag}><AddressLine1Txt>1 Main St</AddressLine1Txt><CityNm>{escape(city)}</CityNm>"
            f"<StateAbbreviationCd>{st}</StateAbbreviationCd><ZIPCd>{z}</ZIPCd></{tag}>")


def header(ein, name, z, year, form, old=False):
    if old:
        return (f"<ReturnHeader><TaxPeriodEndDate>{year}-12-31</TaxPeriodEndDate><ReturnType>{form}</ReturnType>"
                f"<Filer><EIN>{ein}</EIN><Name><BusinessNameLine1>{escape(name)}</BusinessNameLine1></Name>"
                f"{addr(z, 'USAddress', old=True)}</Filer><TaxYear>{year}</TaxYear></ReturnHeader>")
    return (f"<ReturnHeader><TaxPeriodEndDt>{year}-12-31</TaxPeriodEndDt><ReturnTypeCd>{form}</ReturnTypeCd>"
            f"<Filer><EIN>{ein}</EIN><BusinessName><BusinessNameLine1Txt>{escape(name)}</BusinessNameLine1Txt>"
            f"</BusinessName>{addr(z, 'USAddress')}</Filer><TaxYr>{year}</TaxYr></ReturnHeader>")


def pf_return(ein, name, z, year, grants, preselected=False, application=None, restrictions=None,
              old=False, amended=False):
    lines = []
    for rname, rz, purpose, amt in grants:
        if old:
            lines.append(
                f"<GrantOrContriPaidDuringYear><RecipientBusinessName><BusinessNameLine1>{escape(rname)}"
                f"</BusinessNameLine1></RecipientBusinessName>{addr(rz, old=True)}"
                f"<RecipientFoundationStatus>PC</RecipientFoundationStatus>"
                f"<PurposeOfGrantOrContribution>{escape(purpose)}</PurposeOfGrantOrContribution>"
                f"<Amount>{amt}</Amount></GrantOrContriPaidDuringYear>")
        else:
            lines.append(
                f"<GrantOrContributionPdDurYrGrp><RecipientBusinessName><BusinessNameLine1Txt>{escape(rname)}"
                f"</BusinessNameLine1Txt></RecipientBusinessName>{addr(rz)}"
                f"<RecipientFoundationStatusTxt>PC</RecipientFoundationStatusTxt>"
                f"<GrantOrContributionPurposeTxt>{escape(purpose)}</GrantOrContributionPurposeTxt>"
                f"<Amt>{amt}</Amt></GrantOrContributionPdDurYrGrp>")
    total = sum(g[3] for g in grants)
    pre = ("<OnlyContributesToPreselected>X</OnlyContributesToPreselected>" if old else
           "<OnlyContriToPreselectedInd>X</OnlyContriToPreselectedInd>") if preselected else ""
    app = ""
    if application or restrictions:
        app = ("<ApplicationSubmissionInfoGrp>"
               + (f"<FormAndInfoAndMaterialsTxt>{escape(application)}</FormAndInfoAndMaterialsTxt>" if application else "")
               + (f"<RestrictionsOnAwardsTxt>{escape(restrictions)}</RestrictionsOnAwardsTxt>" if restrictions else "")
               + "</ApplicationSubmissionInfoGrp>")
    total_tag = "TotalGrantOrContriPaidDuringYear" if old else "TotalGrantOrContriPdDurYrAmt"
    amend = "<AmendedReturnInd>X</AmendedReturnInd>" if amended else ""
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<Return xmlns="{NS}" returnVersion="2023v4.0">'
            f"{header(ein, name, z, year, '990PF', old)}<ReturnData documentCnt=\"1\"><IRS990PF>{amend}"
            f"<FMVAssetsEOYAmt>{total * 20}</FMVAssetsEOYAmt><SupplementaryInformationGrp>{pre}{app}"
            f"{''.join(lines)}<{total_tag}>{total}</{total_tag}></SupplementaryInformationGrp>"
            f"</IRS990PF></ReturnData></Return>")


def sched_i_return(ein, name, z, year, grants):
    rows = "".join(
        f"<RecipientTable><RecipientEIN>{rein}</RecipientEIN><RecipientBusinessName><BusinessNameLine1Txt>"
        f"{escape(ORGS[rein][0].title())}</BusinessNameLine1Txt></RecipientBusinessName>{addr(ORGS[rein][1], 'USAddress')}"
        f"<IRCSectionDesc>501(c)(3)</IRCSectionDesc><CashGrantAmt>{amt}</CashGrantAmt>"
        f"<PurposeOfGrantTxt>{escape(purpose)}</PurposeOfGrantTxt></RecipientTable>"
        for rein, purpose, amt in grants)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<Return xmlns="{NS}" returnVersion="2023v4.0">'
            f"{header(ein, name, z, year, '990')}<ReturnData documentCnt=\"2\"><IRS990>"
            f"<TotalAssetsEOYAmt>40000000</TotalAssetsEOYAmt></IRS990><IRS990ScheduleI>{rows}</IRS990ScheduleI>"
            f"</ReturnData></Return>")


def ez_return():
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<Return xmlns="{NS}">'
            f"{header('900000099', 'Small Garden Club Inc', '14850', 2024, '990EZ')}"
            f"<ReturnData><IRS990EZ><TotalRevenueAmt>12000</TotalRevenueAmt></IRS990EZ></ReturnData></Return>")


def build_returns():
    files = {}
    oid = iter(range(1, 1000))

    def name_for(year):
        return f"{year + 1}{next(oid):014d}"   # IRS-like 18-digit object id

    for year in (2022, 2023, 2024):
        lakeview = [
            ("NYS Association of County Health Officials Inc", "12207", "Public health workforce training", 150000),
            ("Common Ground Health", "14607", "Population health data collaborative", 200000),
            ("Steuben Rural Health Network Inc", "14810", "Rural health access program", 100000),
            ("Adirondack Health Institute Inc.", "12983", "Community health worker training", 120000),
        ]
        if year == 2024:
            lakeview.append(("Healthy Capitol District Initiative", "12207", "General support", 90000))
        files[f"{name_for(year)}_public.xml"] = pf_return(
            "900000001", "Lakeview Health Fund", "14607", year, lakeview,
            application="Letter of inquiry through the website; full proposals by invitation.",
            restrictions="Grants to 501(c)(3) organizations in New York State only.")

        national = [
            ("University Hospital System", "94103", "Biomedical research", 2_500_000),
            ("Philadelphia Health Research Institute", "19103", "Health services research", 2_000_000),
            ("Pacific Health Policy Institute", "94103", "Public health policy and practice", 1_500_000),
        ]
        if year >= 2023:   # only two NY grants, so mission is judged on ALL its grants
            national.append(("New York State Association of County Health Officials", "12207",
                             "Public health emergency preparedness", 1_500_000))
        files[f"{name_for(year)}_public.xml"] = pf_return(
            "900000002", "National Health Research Trust", "20001", year, national,
            application="Online application; see website for deadlines.",
            restrictions="No grants to individuals. No grants for lobbying or political campaigns.")

        files[f"{name_for(year)}_public.xml"] = pf_return(
            "900000003", "Smith Family Foundation", "14830", year, [
                ("CASA-Trinity Inc", "14901", "General support", 60000),
                ("Institute For Human Services", "14810", "Youth programs", 50000),
                ("Southern Tier Recovery Ctr Inc", "14830", "Recovery housing", 80000),
                ("Steuben Rural Health Network Inc", "14810", "General operating", 100000),
            ], preselected=True)

        files[f"{name_for(year)}_public.xml"] = pf_return(
            "900000004", "Hudson Arts Foundation", "10001", year, [
                ("Brooklyn Arts Collective Inc", "11201", "Artist residencies", 400000),
                ("Manhattan Museum of Modern Craft", "10001", "Exhibitions", 600000),
            ], application="Proposals accepted year round.", old=(year == 2022))

        files[f"{name_for(year)}_public.xml"] = pf_return(
            "900000005", "Tiny Giving Fund", "14850", year, [
                ("Mental Health Association in Tompkins County", "14850", "Crisis services", 40000),
            ], application="Email the trustee.")

        files[f"{name_for(year)}_public.xml"] = sched_i_return(
            "900000006", "Finger Lakes Community Foundation Inc", "14901", year, [
                ("910000006", "Opioid prevention and overdose response", 120000),
                ("910000007", "Family services", 75000),
                ("910000008", "Peer recovery support", 150000),
                ("910000009", "Farmer mental health outreach", 60000),
                ("910000010", "Crisis line", 90000),
            ])

    # Amended Lakeview 2024 return, filed later: adds one grant. Must REPLACE the original.
    amended = [
        ("NYS Association of County Health Officials Inc", "12207", "Public health workforce training", 150000),
        ("Common Ground Health", "14607", "Population health data collaborative", 200000),
        ("Steuben Rural Health Network Inc", "14810", "Rural health access program", 100000),
        ("Adirondack Health Institute Inc.", "12983", "Community health worker training", 120000),
        ("Healthy Capitol District Initiative", "12207", "General support", 90000),
        ("Rochester Youth Services Inc", "14607", "Youth health education", 60000),
    ]
    files[f"2026{999:014d}_public.xml"] = pf_return(
        "900000001", "Lakeview Health Fund", "14607", 2024, amended, amended=True,
        application="Letter of inquiry through the website; full proposals by invitation.",
        restrictions="Grants to 501(c)(3) organizations in New York State only.")

    files[f"{name_for(2019)}_public.xml"] = pf_return(
        "900000007", "Dormant Family Foundation", "14203", 2019, [
            ("Rochester Youth Services Inc", "14607", "Youth programs", 500000)])
    files[f"{name_for(2024)}_public.xml"] = ez_return()
    return files


def main():
    XML_DIR.mkdir(exist_ok=True)
    for old in XML_DIR.glob("*.xml"):
        old.unlink()
    for fname, body in build_returns().items():
        (XML_DIR / fname).write_text(body, encoding="utf-8")

    with open(HERE / "bmf_fixture.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["EIN", "NAME", "ICO", "STREET", "CITY", "STATE", "ZIP", "GROUP", "SUBSECTION", "AFFILIATION",
                    "CLASSIFICATION", "RULING", "DEDUCTIBILITY", "FOUNDATION", "ACTIVITY", "ORGANIZATION",
                    "STATUS", "TAX_PERIOD", "ASSET_CD", "INCOME_CD", "FILING_REQ_CD", "PF_FILING_REQ_CD",
                    "ACCT_PD", "ASSET_AMT", "INCOME_AMT", "REVENUE_AMT", "NTEE_CD", "SORT_NAME"])
        for ein, (name, z, ntee, rev, sub, fnd) in ORGS.items():
            city, st, *_ = ZIPS[z]
            w.writerow([ein, name, "", "1 MAIN ST", city.upper(), st, f"{z}-0000", "0000", sub, "3", "1000",
                        "199001", "1", fnd, "000000000", "1", "01", "202312", "5", "5", "01", "0", "12",
                        rev * 2, rev, rev, ntee, ""])

    with open(HERE / "zcta_county_fixture.txt", "w", newline="") as f:
        f.write("GEOID_ZCTA5_20|GEOID_COUNTY_20|NAMELSAD_COUNTY_20|AREALAND_PART\n")
        f.write("|36101|Steuben County|0\n")                         # county-only row: skipped
        for z, (_, _, county, fips, _) in ZIPS.items():
            f.write(f"{z}|{fips}|{county}|5000000\n")
        f.write("14830|36015|Chemung County|100000\n")                # small sliver: Steuben keeps 14830

    with open(HERE / "ruca_fixture.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ZIP_CODE", "STATE", "ZIP_TYPE", "RUCA1", "RUCA2"])
        for z, (_, st, _, _, ruca) in ZIPS.items():
            w.writerow([z, st, "Zip Code Area", ruca, float(ruca)])

    grants_gov = [
        {"errorcode": 0, "data": {"hitCount": 2, "oppHits": [
            {"id": "350001", "number": "HRSA-27-001", "title": "Public Health Infrastructure Workforce (synthetic)",
             "agencyCode": "HHS-HRSA", "agency": "Health Resources and Services Administration",
             "openDate": "10/01/2026", "closeDate": "01/15/2027", "oppStatus": "posted", "alnist": ["93.000"]},
            {"id": "350002", "number": "CDC-RFA-27-002", "title": "Community Health Training Centers (synthetic)",
             "agencyCode": "HHS-CDC", "agency": "Centers for Disease Control and Prevention",
             "openDate": "", "closeDate": "", "oppStatus": "forecasted", "alnist": ["93.001"]}]}},
        {"errorcode": 0, "data": {"hitCount": 1, "oppHits": [
            {"id": "350001", "number": "HRSA-27-001", "title": "Public Health Infrastructure Workforce (synthetic)",
             "agencyCode": "HHS-HRSA", "agency": "Health Resources and Services Administration",
             "openDate": "10/01/2026", "closeDate": "01/15/2027", "oppStatus": "posted", "alnist": ["93.000"]}]}},
        {"errorcode": 0, "data": {"hitCount": 1, "oppHits": [
            {"id": "350003", "number": "HRSA-27-003", "title": "Rural Communities Opioid Response (synthetic)",
             "agencyCode": "HHS-HRSA", "agency": "Health Resources and Services Administration",
             "openDate": "11/01/2026", "closeDate": "02/28/2027", "oppStatus": "posted", "alnist": ["93.002"]}]}},
    ]
    (HERE / "grantsgov_fixture.json").write_text(json.dumps(grants_gov, indent=1))
    print(f"Wrote {len(list(XML_DIR.glob('*.xml')))} XML returns and reference fixtures to {HERE}")


if __name__ == "__main__":
    main()
