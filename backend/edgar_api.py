"""REST-API-oriented EDGAR query helpers (distinct from agent tools in tools.py)."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

EDGAR_SEARCH_API = "https://efts.sec.gov/LATEST/search-index"
EDGAR_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar"
_HEADERS = {"User-Agent": "edgar-agent research@example.com"}


def _filing_url(acc_num: str) -> str:
    cik = acc_num.split("-")[0]
    path = acc_num.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{path}/{acc_num}-index.htm"


def _edgar_search(params: dict) -> dict:
    try:
        resp = httpx.get(EDGAR_SEARCH_API, params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "hits": {"hits": [], "total": {"value": 0}}}


def _parse_display_name(display_names: list) -> str:
    """Extract clean company name from EDGAR display_names list."""
    raw = (display_names or [""])[0]
    return raw.split("  (")[0].strip()


def search_filings(
    q: Optional[str] = None,
    entity: Optional[str] = None,
    form: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    offset: int = 0,
    size: int = 20,
) -> dict:
    params: dict = {
        "_source": "file_date,period_ending,display_names,file_num,form,biz_locations,inc_states,ciks",
        "from": offset,
        "size": max(size, 1),
    }
    if q:
        params["q"] = q
    if entity:
        params["q"] = f'"{entity}"'
    if form:
        params["forms"] = form
    if from_date or to_date:
        params["dateRange"] = "custom"
        if from_date:
            params["startdt"] = from_date
        if to_date:
            params["enddt"] = to_date

    data = _edgar_search(params)
    hits_block = data.get("hits", {})
    total = hits_block.get("total", {}).get("value", 0)

    items = []
    for hit in hits_block.get("hits", []):
        src = hit.get("_source", {})
        raw_id = hit.get("_id", "")
        acc_num = raw_id.split(":")[0] if ":" in raw_id else raw_id
        cik = (src.get("ciks") or [""])[0].lstrip("0") or "0"
        items.append({
            "id": acc_num,
            "entity_name": _parse_display_name(src.get("display_names", [])),
            "cik": cik,
            "form_type": src.get("form", ""),
            "period_of_report": src.get("period_ending", ""),
            "file_date": src.get("file_date", ""),
            "biz_location": (src.get("biz_locations") or [""])[0],
            "inc_states": ", ".join(src.get("inc_states") or []),
            "url": _filing_url(acc_num) if acc_num else "",
        })

    return {"items": items, "total": total}


def search_companies_by_entity(q: str, limit: int = 20) -> dict:
    """Lookup filers by registered entity name via EDGAR company search (registrant-name filter)."""
    params = {
        "company": q,
        "action": "getcompany",
        "type": "10-K",
        "owner": "include",
        "count": min(limit, 100),
        "search_text": "",
        "output": "atom",
    }
    try:
        resp = httpx.get(EDGAR_BROWSE, params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"items": [], "total": 0}

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return {"items": [], "total": 0}

    seen: set[str] = set()
    items = []
    for entry in root.findall("atom:entry", ns):
        name = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        id_url = entry.findtext("atom:id", default="", namespaces=ns) or ""
        qs = parse_qs(urlparse(id_url).query)
        raw_cik = (qs.get("CIK") or qs.get("cik") or [""])[0]
        cik = raw_cik.lstrip("0") or "0"

        if name and cik and cik not in seen:
            seen.add(cik)
            items.append({
                "entity_name": name,
                "cik": cik,
                "biz_location": "",
                "inc_states": "",
            })
        if len(items) >= limit:
            break

    return {"items": items, "total": len(items)}


def search_companies(q: str, limit: int = 20) -> dict:
    params: dict = {
        "q": f'"{q}"',
        "_source": "display_names,ciks,biz_locations,inc_states",
        "forms": "10-K",
        "size": min(limit * 4, 100),
    }
    data = _edgar_search(params)
    hits = data.get("hits", {}).get("hits", [])

    seen: set[str] = set()
    items = []
    for hit in hits:
        src = hit.get("_source", {})
        name = _parse_display_name(src.get("display_names", []))
        cik = (src.get("ciks") or [""])[0].lstrip("0") or "0"
        if name and cik not in seen:
            seen.add(cik)
            items.append({
                "entity_name": name,
                "cik": cik,
                "biz_location": (src.get("biz_locations") or [""])[0],
                "inc_states": ", ".join(src.get("inc_states") or []),
            })
        if len(items) >= limit:
            break

    return {"items": items, "total": len(items)}


def get_filing_aggregates(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    form: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    params: dict = {
        "_source": "file_date,form",
        "size": 500,
    }
    if q:
        params["q"] = q
    if form:
        params["forms"] = form
    if from_date or to_date:
        params["dateRange"] = "custom"
        if from_date:
            params["startdt"] = from_date
        if to_date:
            params["enddt"] = to_date

    data = _edgar_search(params)
    hits_block = data.get("hits", {})
    total = hits_block.get("total", {}).get("value", 0)
    hits = hits_block.get("hits", [])

    monthly: dict[str, int] = defaultdict(int)
    for hit in hits:
        file_date = hit.get("_source", {}).get("file_date", "")
        if file_date and len(file_date) >= 7:
            monthly[file_date[:7]] += 1

    chart_data = [
        {"date": f"{month}-01", "count": count}
        for month, count in sorted(monthly.items())
    ]
    return {"data": chart_data, "totalFilings": total}
