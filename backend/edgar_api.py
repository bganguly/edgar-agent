"""REST-API-oriented EDGAR query helpers (distinct from agent tools in tools.py)."""

from collections import defaultdict
from typing import Optional

import re

import httpx
from bs4 import BeautifulSoup, NavigableString

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
    size: int = 10,
) -> dict:
    # EDGAR EFTS ignores both `size` and `from` Elasticsearch params; it always
    # returns ~100 hits regardless. Omit them and do pagination client-side.
    params: dict = {
        "_source": "file_date,period_ending,display_names,file_num,form,biz_locations,inc_states,ciks",
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

    all_items = []
    for hit in hits_block.get("hits", []):
        src = hit.get("_source", {})
        raw_id = hit.get("_id", "")
        acc_num = raw_id.split(":")[0] if ":" in raw_id else raw_id
        cik = (src.get("ciks") or [""])[0].lstrip("0") or "0"
        all_items.append({
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

    return {"items": all_items[offset : offset + size], "total": len(all_items)}


def _extract_cik(href: str) -> str:
    """Extract numeric CIK from an EDGAR href, handling both & and &amp; encoding."""
    m = re.search(r'CIK=(\d+)', href, re.IGNORECASE)
    return (m.group(1).lstrip("0") or "0") if m else ""


def search_companies_by_entity(q: str, limit: int = 20) -> dict:
    """Lookup filers by registered entity name via EDGAR company search HTML (registrant-name filter)."""
    params = {
        "company": q,
        "action": "getcompany",
        "owner": "include",
        "count": min(limit, 100),
        "search_text": "",
    }
    try:
        resp = httpx.get(EDGAR_BROWSE, params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return {"items": [], "total": 0}

    soup = BeautifulSoup(resp.text, "lxml")

    # When exactly one company matches, EDGAR skips the list and shows that
    # company's filings page directly. Detect this by looking for companyName span.
    company_span = soup.find("span", class_="companyName")
    if company_span:
        # Name: first non-empty text node, or full span text before "CIK" as fallback
        name = next(
            (c.strip() for c in company_span.children if isinstance(c, NavigableString) and c.strip()),
            "",
        )
        if not name:
            name = company_span.get_text(separator=" ").split("CIK")[0].strip()

        cik_link = company_span.find("a")
        href = cik_link.get("href", "") if cik_link else ""
        cik = _extract_cik(href)

        if name and cik:
            return {"items": [{"entity_name": name, "cik": cik, "biz_location": "", "inc_states": ""}], "total": 1}
        return {"items": [], "total": 0}

    # Multiple-company list: tableFile2 with CIK / Company / State columns.
    table = soup.find("table", class_="tableFile2")
    if not table:
        return {"items": [], "total": 0}

    items = []
    seen: set[str] = set()
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        cik_link = cells[0].find("a")
        href0 = cik_link.get("href", "") if cik_link else ""
        cik = _extract_cik(href0) or (cik_link.get_text(strip=True).lstrip("0") or "0" if cik_link else "")

        name = next(
            (c.strip() for c in cells[1].children if isinstance(c, NavigableString) and c.strip()),
            "",
        )

        state_link = cells[2].find("a")
        state = state_link.get_text(strip=True) if state_link else ""

        if name and cik and cik not in seen:
            seen.add(cik)
            items.append({
                "entity_name": name,
                "cik": cik,
                "biz_location": "",
                "inc_states": state,
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
