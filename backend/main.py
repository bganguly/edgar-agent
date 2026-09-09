from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import chat, companies, filings

app = FastAPI(title="EDGAR Agent", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router)
app.include_router(filings.router)
app.include_router(chat.router)


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
