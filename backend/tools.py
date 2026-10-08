import re
import httpx
from bs4 import BeautifulSoup

TOOL_DEFINITIONS = [
    {
        "name": "search_edgar",
        "description": (
            "Search SEC EDGAR for 10-K annual filings for a given company. "
            "Returns a list of filing index URLs that can be fetched with fetch_filing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The name of the public company to search for (e.g. 'Apple', 'Tesla Inc').",
                }
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "fetch_filing",
        "description": (
            "Fetch and extract narrative text from a SEC EDGAR 10-K filing URL. "
            "Handles Inline XBRL (iXBRL) documents. "
            "Pass an optional 'section' (e.g. 'Item 1A', 'Item 7') to jump directly to that part "
            "instead of returning text from the top of the document."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The EDGAR filing index URL (returned by search_edgar).",
                },
                "section": {
                    "type": "string",
                    "description": (
                        "Optional section heading to jump to, e.g. 'Item 1A', 'Item 7', 'Item 8'. "
                        "When provided, returns ~8000 chars starting from that section."
                    ),
                },
            },
            "required": ["url"],
        },
    },
]

_HEADERS = {"User-Agent": "edgar-agent research@example.com"}
_MAX_CHARS = 12000
_SECTION_CHARS = 8000


def _normalize_edgar_url(href: str) -> str:
    """Strip the EDGAR inline-XBRL viewer wrapper if present, returning the raw doc URL."""
    # /ix?doc=/Archives/... → https://www.sec.gov/Archives/...
    if "/ix?doc=" in href:
        raw = href.split("/ix?doc=", 1)[1]
        if not raw.startswith("http"):
            raw = "https://www.sec.gov" + raw
        return raw
    return href


def _resolve_primary_document(index_url: str) -> str:
    """Given a -index.htm URL, fetch the filing index and return the primary HTM document URL."""
    try:
        resp = httpx.get(index_url, headers=_HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # The filing index table lists documents; the primary document is the first
        # row whose Type column matches 10-K (or 10-K/A).
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) >= 4:
                doc_type = cells[3].get_text(strip=True)
                if doc_type in ("10-K", "10-K/A"):
                    link = cells[2].find("a")
                    if link and link.get("href"):
                        href = link["href"]
                        if href.startswith("/"):
                            href = "https://www.sec.gov" + href
                        return _normalize_edgar_url(href)

        # Fallback: first .htm link that is not the index itself
        base = index_url.rsplit("/", 1)[0]
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".htm") and "index" not in href.lower():
                if href.startswith("/"):
                    href = "https://www.sec.gov" + href
                elif not href.startswith("http"):
                    href = base + "/" + href
                return _normalize_edgar_url(href)
    except Exception:
        pass
    return index_url


def _strip_ixbrl(soup: BeautifulSoup) -> None:
    """Remove iXBRL noise in-place, keeping narrative text."""
    # Remove the entire ix:header block (machine-readable XBRL taxonomy links, no human text)
    for tag in soup.find_all(re.compile(r"^ix:header$", re.I)):
        tag.decompose()

    # Remove hidden divs used as XBRL containers (e.g. <div style="display:none">)
    for tag in soup.find_all("div", style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()

    # Unwrap inline XBRL wrapper tags — they surround readable text, so keep contents
    for tag_name in ("ix:nonnumeric", "ix:nonfraction", "ix:continuation", "ix:exclude",
                     "ix:footnote", "ix:relationship", "xbrli:context", "xbrli:unit"):
        for tag in soup.find_all(re.compile(rf"^{re.escape(tag_name)}$", re.I)):
            tag.unwrap()

    # Remove any remaining ix: or xbrl namespace tags that carry no readable text
    for tag in soup.find_all(re.compile(r"^(ix:|xbrli:|link:|label:)", re.I)):
        tag.decompose()


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()
    _strip_ixbrl(soup)
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
    # Collapse runs of repeated short lines (XBRL artifact: many single-char lines)
    cleaned = []
    for ln in lines:
        if cleaned and len(ln) <= 2 and len(cleaned[-1]) <= 2:
            continue
        cleaned.append(ln)
    return "\n".join(cleaned)


def _find_section(text: str, section: str) -> str:
    """Return text starting from the section body (skips TOC entries)."""
    pattern = re.compile(
        r"(?:^|\n)\s*" + re.escape(section) + r"\b",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        snippet = text[m.start():m.start() + 200].strip()
        lines = [l.strip() for l in snippet.splitlines() if l.strip()]
        # TOC entries: within the first 4 non-empty lines there is a bare page number
        toc_hit = any(re.fullmatch(r"\d{1,3}", ln) for ln in lines[1:4])
        if toc_hit:
            continue
        return text[m.start():][:_SECTION_CHARS]
    # Looser pass: any occurrence not a pure TOC entry
    for m in re.finditer(re.escape(section), text, re.IGNORECASE):
        snippet = text[m.start():m.start() + 200].strip()
        lines = [l.strip() for l in snippet.splitlines() if l.strip()]
        toc_hit = any(re.fullmatch(r"\d{1,3}", ln) for ln in lines[1:4])
        if toc_hit:
            continue
        return text[m.start():][:_SECTION_CHARS]
    return f"Section '{section}' not found in this filing."


def search_edgar(company_name: str) -> str:
    try:
        resp = httpx.get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={
                "company": company_name,
                "CIK": "",
                "type": "10-K",
                "dateb": "",
                "owner": "include",
                "count": "10",
                "search_text": "",
                "action": "getcompany",
            },
            headers=_HEADERS,
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        return f"EDGAR search failed: {e}"

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for row in soup.select("table.tableFile2 tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = cells[1].find("a")
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if not href.startswith("/Archives/"):
            continue
        filing_date = cells[3].get_text(strip=True)
        doc_url = "https://www.sec.gov" + href
        results.append(f"- {company_name} | Filed: {filing_date} | URL: {doc_url}")
        if len(results) >= 5:
            break

    if not results:
        return f"No 10-K filings found for '{company_name}'."
    return "\n".join(results)


def fetch_filing(url: str, section: str | None = None) -> str:
    # If given an index page, resolve to the primary document first
    if url.endswith("-index.htm") or url.endswith("-index.html") or "index" in url.split("/")[-1].lower():
        url = _resolve_primary_document(url)

    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return f"Failed to fetch filing: {e}"

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type or url.lower().endswith((".htm", ".html")):
        soup = BeautifulSoup(resp.text, "lxml")
        text = _extract_text(soup)
    else:
        text = resp.text

    if section:
        return _find_section(text, section)

    return text[:_MAX_CHARS] if len(text) > _MAX_CHARS else text


def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "search_edgar":
        return search_edgar(tool_input["company_name"])
    elif tool_name == "fetch_filing":
        return fetch_filing(tool_input["url"], tool_input.get("section"))
    else:
        return f"Unknown tool: {tool_name}"
