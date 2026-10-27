"""Federal opportunities from the Grants.gov Search2 API (free, no key).

POST https://api.grants.gov/v1/api/search2  with JSON like
  {"keyword": "rural health", "oppStatuses": "forecasted|posted", "rows": 50}
or  {"aln": "93.912", ...}

Keyword recall is uneven. Once you know which programs matter, add their
Assistance Listing Numbers (ALNs) to the client profile under grants_gov.alns.

New York State opportunities are NOT here. They come from SFS Vendor Portal
email alerts, filed under the Gmail label "Grant Alerts/NYS SFS" in Adam's
Appius inbox. A scraper is a stretch goal.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from prospector import USER_AGENT

URL = "https://api.grants.gov/v1/api/search2"


def _post(body: dict, cache_dir: Path | None, pause: float) -> dict:
    import hashlib

    import requests

    key = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{key}.json"
        if cached.exists():
            return json.loads(cached.read_text())
    r = requests.post(URL, json=body, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if cache_dir:
        cached.write_text(json.dumps(data))
    time.sleep(pause)
    return data


def parse_hits(payload: dict, query_label: str) -> list[dict]:
    hits = (payload.get("data") or {}).get("oppHits") or []
    out = []
    for h in hits:
        alns = h.get("alnist") or h.get("cfdaList") or []
        out.append({
            "opportunity_id": h.get("id"), "number": h.get("number"), "title": h.get("title"),
            "agency": h.get("agency") or h.get("agencyName") or h.get("agencyCode"),
            "status": h.get("oppStatus"), "open_date": h.get("openDate"), "close_date": h.get("closeDate"),
            "alns": ", ".join(alns) if isinstance(alns, list) else str(alns),
            "found_by": query_label,
            "link": f"https://www.grants.gov/search-results-detail/{h.get('id')}" if h.get("id") else "",
        })
    return out


def search_client(client: dict, cache_dir: Path | None = None, rows: int = 50, pause: float = 1.0,
                  offline_payloads: list[dict] | None = None) -> list[dict]:
    """Run every keyword and ALN in the client profile. De-duplicates by opportunity number.
    `offline_payloads` lets tests and the demo run without the network."""
    spec = client.get("grants_gov") or {}
    queries = [("keyword", k) for k in spec.get("keywords", [])] + [("aln", a) for a in spec.get("alns", [])]
    seen, out = set(), []
    for i, (kind, value) in enumerate(queries):
        if offline_payloads is not None:
            if i >= len(offline_payloads):
                break
            payload = offline_payloads[i]
        else:
            payload = _post({kind: value, "oppStatuses": "forecasted|posted", "rows": rows}, cache_dir, pause)
        for hit in parse_hits(payload, f"{kind}: {value}"):
            k = hit["number"] or hit["opportunity_id"]
            if k in seen:
                continue
            seen.add(k)
            out.append(hit)
    return out
