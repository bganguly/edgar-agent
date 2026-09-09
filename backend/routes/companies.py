from fastapi import APIRouter, HTTPException

from edgar_api import search_companies, search_companies_by_entity

router = APIRouter()


@router.get("/companies")
def companies(q: str = "", page: int = 1, pageSize: int = 10):
    pageSize = min(pageSize, 10)
    offset = (page - 1) * pageSize
    try:
        result = search_companies_by_entity(q or "a", limit=100)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"EDGAR unavailable: {e}")
    items = result["items"]
    return {"items": items[offset : offset + pageSize], "total": len(items), "page": page, "pageSize": pageSize}


@router.get("/companies/search")
def companies_search(q: str = "", page: int = 1, pageSize: int = 10):
    pageSize = min(pageSize, 10)
    offset = (page - 1) * pageSize
    try:
        result = search_companies(q or "a", limit=100)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"EDGAR unavailable: {e}")
    items = result["items"]
    return {"items": items[offset : offset + pageSize], "total": len(items), "page": page, "pageSize": pageSize}
