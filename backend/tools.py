import httpx
from bs4 import BeautifulSoup

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&dateRange=custom&startdt=2020-01-01&forms=10-K"
EDGAR_FULL_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&forms=10-K"
EDGAR_SEARCH_API = "https://efts.sec.gov/LATEST/search-index"

TOOL_DEFINITIONS = [
    {
        "name": "search_edgar",
        "description": (
            "Search SEC EDGAR for 10-K annual filings for a given company. "
            "Returns a list of filing URLs that can be fetched with fetch_filing."
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
            "Fetch and extract text from a SEC EDGAR 10-K filing URL. "
            "Returns the first ~12000 characters of the filing's readable text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The EDGAR filing URL to fetch (returned by search_edgar).",
                }
            },
            "required": ["url"],
        },
    },
]


def search_edgar(company_name: str) -> str:
    params = {
        "q": f'"{company_name}"',
        "forms": "10-K",
        "_source": "file_date,period_of_report,entity_name,file_num,form_type,biz_location,inc_states,file_type",
        "dateRange": "custom",
        "startdt": "2019-01-01",
    }
    headers = {"User-Agent": "edgar-agent research@example.com"}
    try:
        resp = httpx.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"EDGAR search failed: {e}"

    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        return f"No 10-K filings found for '{company_name}'."

    results = []
    for hit in hits[:5]:
        src = hit.get("_source", {})
        entity = src.get("entity_name", "Unknown")
        period = src.get("period_of_report", "")
        file_num = src.get("file_num", "")
        accession = hit.get("_id", "").replace(":", "-")
        viewer_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={file_num}&type=10-K&dateb=&owner=include&count=10"
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{accession.split('-')[0]}/{accession.replace('-','')}/{accession}-index.htm" if accession else ""
        results.append(f"- {entity} | Period: {period} | URL: {doc_url or viewer_url}")

    return "\n".join(results)


def fetch_filing(url: str) -> str:
    headers = {"User-Agent": "edgar-agent research@example.com"}
    try:
        resp = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return f"Failed to fetch filing: {e}"

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type or url.endswith(".htm") or url.endswith(".html"):
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "meta", "link"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    else:
        text = resp.text

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned = "\n".join(lines)
    return cleaned[:12000] if len(cleaned) > 12000 else cleaned


def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "search_edgar":
        return search_edgar(tool_input["company_name"])
    elif tool_name == "fetch_filing":
        return fetch_filing(tool_input["url"])
    else:
        return f"Unknown tool: {tool_name}"
