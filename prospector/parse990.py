"""Parse IRS e-file XML (990-PF and Form 990 Schedule I).

Element names changed across schema years, so lookups go by the element's local
name (ignoring the namespace) and try several known names in order. When a real
filing has a name that isn't listed here, add it to the tuple and log it.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterable

# ---- name variants by schema year (newest first) ---------------------------
PF_GRANT_GROUPS = ("GrantOrContributionPdDurYrGrp", "GrantOrContriPaidDuringYear",
                   "GrantOrContributionPaidDuringYear")
PF_PURPOSE = ("GrantOrContributionPurposeTxt", "PurposeOfGrantOrContribution", "PurposeOfGrantTxt")
PF_AMOUNT = ("Amt", "Amount")
PF_STATUS = ("RecipientFoundationStatusTxt", "RecipientFoundationStatus")
PF_PRESELECTED = ("OnlyContriToPreselectedInd", "OnlyContributesToPreselected")
PF_APPLICATION = ("ApplicationSubmissionInfoGrp", "ApplicationSubmissionInformation")
PF_APP_FIELDS = ("FormAndInfoAndMaterialsTxt", "SubmissionDeadlinesTxt", "RecipientEmailAddressTxt",
                 "FormAndInformationAndMaterials", "SubmissionDeadlines")
PF_RESTRICTIONS = ("RestrictionsOnAwardsTxt", "RestrictionsOnAwards")
PF_TOTAL_PAID = ("TotalGrantOrContriPdDurYrAmt", "TotalGrantOrContriPaidDuringYear",
                 "ContriPaidRptdRevAndExpnssAmt")
PF_ASSETS = ("FMVAssetsEOYAmt", "TotalAssetsEOYAmt", "FMVAssetsEOY")

SI_RECIPIENT = ("RecipientTable", "RecipientTable2", "GrantsOtherAsstToOrgsInUSGrp")
SI_EIN = ("RecipientEIN", "EINOfRecipient")
SI_CASH = ("CashGrantAmt", "AmountOfCashGrant")
SI_NONCASH = ("NonCashAssistanceAmt", "AmountOfNonCashAssistance")
SI_PURPOSE = ("PurposeOfGrantTxt", "PurposeOfGrant")

NAME_TAGS = ("BusinessNameLine1Txt", "BusinessNameLine1")
NAME_TAGS_2 = ("BusinessNameLine2Txt", "BusinessNameLine2")
PERSON_TAGS = ("RecipientPersonNm", "RecipientPersonName")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find(el: ET.Element | None, names: Iterable[str]) -> ET.Element | None:
    """First descendant whose local name is in `names` (checked in order)."""
    if el is None:
        return None
    names = tuple(names)
    for name in names:
        for child in el.iter():
            if local(child.tag) == name:
                return child
    return None


def find_all(el: ET.Element | None, names: Iterable[str]) -> list[ET.Element]:
    if el is None:
        return []
    names = set(names)
    return [c for c in el.iter() if local(c.tag) in names]


def text(el: ET.Element | None, names: Iterable[str], default: str | None = None) -> str | None:
    found = find(el, names)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def money(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def flag(el: ET.Element | None, names: Iterable[str]) -> int:
    v = (text(el, names) or "").strip().upper()
    return 1 if v in ("X", "1", "TRUE", "Y", "YES") else 0


def org_name(el: ET.Element | None) -> str | None:
    """Business name lines 1 + 2, or a person's name."""
    if el is None:
        return None
    biz = None
    for c in el:
        if local(c.tag) in ("RecipientBusinessName", "BusinessName", "RecipientNameBusiness"):
            biz = c
            break
    if biz is not None:
        n1 = text(biz, NAME_TAGS) or ""
        n2 = text(biz, NAME_TAGS_2) or ""
        return " ".join(p for p in (n1, n2) if p).strip() or None
    return text(el, PERSON_TAGS)


def address(el: ET.Element | None) -> dict:
    if el is None:
        return {"city": None, "state": None, "zip": None}
    us = find(el, ("RecipientUSAddress", "USAddress", "AddressUS"))
    foreign = find(el, ("RecipientForeignAddress", "ForeignAddress", "AddressForeign"))
    if us is not None:
        z = text(us, ("ZIPCd", "ZIPCode"))
        return {"city": text(us, ("CityNm", "City")),
                "state": text(us, ("StateAbbreviationCd", "State")),
                "zip": z[:5] if z else None}
    if foreign is not None:
        return {"city": text(foreign, ("CityNm", "City")), "state": "FOREIGN", "zip": None}
    return {"city": None, "state": None, "zip": None}


def parse_header(root: ET.Element) -> dict:
    header = find(root, ("ReturnHeader",))
    filer = find(header, ("Filer",))
    name_el = find(filer, ("BusinessName", "Name"))
    us = find(filer, ("USAddress",))
    tax_year = text(header, ("TaxYr", "TaxYear"))
    period_end = text(header, ("TaxPeriodEndDt", "TaxPeriodEndDate"))
    if not tax_year and period_end:
        tax_year = period_end[:4]
    z = text(us, ("ZIPCd", "ZIPCode"))
    return {
        "ein": text(filer, ("EIN",)),
        "name": " ".join(p for p in (text(name_el, NAME_TAGS), text(name_el, NAME_TAGS_2)) if p) or None,
        "form": (text(header, ("ReturnTypeCd", "ReturnType")) or "").replace("-", "").upper(),
        "tax_year": int(tax_year) if tax_year and tax_year.isdigit() else None,
        "tax_period_end": period_end,
        "state": text(us, ("StateAbbreviationCd", "State")),
        "city": text(us, ("CityNm", "City")),
        "zip": z[:5] if z else None,
        "amended": flag(root, ("AmendedReturnInd", "AmendedReturn")),
    }


def parse_return(xml_bytes: bytes, object_id: str, source: str = "") -> tuple[dict | None, list[dict], list[str]]:
    """Parse one return. Returns (filing, grants, warnings).
    filing is None when the return is neither a 990-PF nor a 990 with Schedule I."""
    warnings: list[str] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        # Some files declare one encoding and use another. Try a lenient decode.
        try:
            root = ET.fromstring(xml_bytes.decode("latin-1").encode("utf-8"))
            warnings.append(f"re-decoded as latin-1 after: {exc}")
        except ET.ParseError:
            return None, [], [f"XML parse error: {exc}"]

    filing = parse_header(root)
    filing.update({"object_id": object_id, "source": source})
    if not filing["ein"]:
        return None, [], ["no filer EIN"]
    data = find(root, ("ReturnData",))
    if filing["form"] == "990PF":
        return _parse_pf(data, filing, warnings)
    if filing["form"] == "990":
        return _parse_schedule_i(data, filing, warnings)
    return None, [], []


def _parse_pf(data, filing, warnings):
    pf = find(data, ("IRS990PF",))
    if pf is None:
        return None, [], warnings + ["990PF return with no IRS990PF section"]
    filing["preselected_only"] = flag(pf, PF_PRESELECTED)
    app = find(pf, PF_APPLICATION)
    app_bits = [text(app, (f,)) for f in PF_APP_FIELDS] if app is not None else []
    filing["application_text"] = " | ".join(b for b in app_bits if b) or None
    filing["restrictions_text"] = text(pf, PF_RESTRICTIONS)
    filing["total_grants_paid"] = money(text(pf, PF_TOTAL_PAID))
    filing["total_assets"] = money(text(pf, PF_ASSETS))

    grants = []
    groups = find_all(pf, PF_GRANT_GROUPS)
    for g in groups:
        amount = money(text(g, PF_AMOUNT))
        name = org_name(g)
        if amount is None:
            warnings.append(f"grant line with no amount: {name!r}")
            continue
        grants.append({
            "object_id": filing["object_id"], "funder_ein": filing["ein"], "tax_year": filing["tax_year"],
            "recipient_name": name, "recipient_ein": None, **address(g),
            "purpose": text(g, PF_PURPOSE), "amount": amount,
            "recipient_status": text(g, PF_STATUS), "source_form": "990PF",
        })
    if filing["total_grants_paid"] and not groups:
        warnings.append("grants paid reported but no itemized grant lines found (check element names or attachment)")
    return filing, grants, warnings


def _parse_schedule_i(data, filing, warnings):
    sched = find(data, ("IRS990ScheduleI",))
    if sched is None:
        return None, [], warnings
    filing["preselected_only"] = 0
    filing["application_text"] = None
    filing["restrictions_text"] = None
    filing["total_assets"] = money(text(find(data, ("IRS990",)), ("TotalAssetsEOYAmt",)))
    grants = []
    for r in find_all(sched, SI_RECIPIENT):
        cash = money(text(r, SI_CASH)) or 0.0
        noncash = money(text(r, SI_NONCASH)) or 0.0
        if cash + noncash <= 0:
            continue
        ein = text(r, SI_EIN)
        grants.append({
            "object_id": filing["object_id"], "funder_ein": filing["ein"], "tax_year": filing["tax_year"],
            "recipient_name": org_name(r), "recipient_ein": ein.replace("-", "") if ein else None,
            **address(r), "purpose": text(r, SI_PURPOSE), "amount": cash + noncash,
            "recipient_status": text(r, ("IRCSectionDesc", "IRCSection")), "source_form": "990SchI",
        })
    filing["total_grants_paid"] = sum(g["amount"] for g in grants)
    return filing, grants, warnings
