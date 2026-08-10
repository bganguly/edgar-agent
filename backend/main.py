import json
import uuid
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent import run_agent
from edgar_api import get_filing_aggregates, search_companies, search_companies_by_entity, search_filings
from sessions import append_message, get_history

app = FastAPI(title="EDGAR Agent", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@app.get("/")
async def root():
    return {
        "service": "EDGAR Agent API",
        "endpoints": {
            "GET /health": "health check",
            "POST /chat": "stream agent response (SSE)",
            "GET /sessions/{session_id}/history": "conversation history",
            "GET /companies": "search filers by registered entity name",
            "GET /companies/search": "full-text search — filers whose 10-K documents mention the term",
            "GET /filings": "search/list 10-K and other filings",
            "GET /filings/count": "count matching filings",
            "GET /aggregates": "filing counts grouped by month",
            "GET /dataset-bounds": "available date range in EDGAR",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/companies")
def companies(q: str = "", page: int = 1, pageSize: int = 10):
    pageSize = min(pageSize, 10)
    offset = (page - 1) * pageSize
    result = search_companies_by_entity(q or "a", limit=100)
    items = result["items"]
    return {"items": items[offset : offset + pageSize], "total": len(items), "page": page, "pageSize": pageSize}


@app.get("/companies/search")
def companies_search(q: str = "", page: int = 1, pageSize: int = 10):
    pageSize = min(pageSize, 10)
    offset = (page - 1) * pageSize
    result = search_companies(q or "a", limit=100)
    items = result["items"]
    return {"items": items[offset : offset + pageSize], "total": len(items), "page": page, "pageSize": pageSize}


@app.get("/filings/count")
def filings_count(
    q: Optional[str] = None,
    entity: Optional[str] = None,
    form: Optional[str] = None,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
):
    result = search_filings(q, entity, form, from_, to, offset=0, size=100)
    return {"total": result["total"]}


@app.get("/filings")
def filings(
    q: Optional[str] = None,
    entity: Optional[str] = None,
    form: Optional[str] = None,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    page: int = 1,
    pageSize: int = 10,
):
    pageSize = min(pageSize, 10)
    offset = (page - 1) * pageSize
    result = search_filings(q, entity, form, from_, to, offset, pageSize)
    return {**result, "page": page, "pageSize": pageSize}


@app.get("/aggregates")
def aggregates(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    form: Optional[str] = None,
    q: Optional[str] = None,
):
    return get_filing_aggregates(from_, to, form, q)


@app.get("/dataset-bounds")
def dataset_bounds():
    return {"from": "1993-01-01", "to": "2025-12-31"}


@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history = get_history(session_id)

    append_message(session_id, {"role": "user", "content": req.message})
    messages = get_history(session_id)

    async def event_stream() -> AsyncGenerator[dict, None]:
        final_messages = None
        async for chunk in run_agent(messages):
            data = json.loads(chunk)
            if data["type"] == "done":
                final_messages = data.get("messages", [])
            else:
                yield {"data": chunk}

        if final_messages:
            # Persist the final assistant message
            for msg in final_messages[len(messages):]:
                append_message(session_id, msg)

        yield {"data": json.dumps({"type": "session_id", "session_id": session_id}) + "\n"}

    return EventSourceResponse(event_stream())


@app.get("/sessions/{session_id}/history")
async def history(session_id: str):
    msgs = get_history(session_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": msgs}
