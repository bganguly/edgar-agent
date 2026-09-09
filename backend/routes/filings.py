from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from edgar_api import get_filing_aggregates, search_filings

router = APIRouter()


@router.get("/filings/count")
def filings_count(
    q: Optional[str] = None,
    entity: Optional[str] = None,
    form: Optional[str] = None,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
):
    try:
        result = search_filings(q, entity, form, from_, to, offset=0, size=100)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"EDGAR unavailable: {e}")
    return {"total": result["total"]}


@router.get("/filings")
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
    try:
        result = search_filings(q, entity, form, from_, to, offset, pageSize)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"EDGAR unavailable: {e}")
    return {**result, "page": page, "pageSize": pageSize}


@router.get("/aggregates")
def aggregates(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    form: Optional[str] = None,
    q: Optional[str] = None,
):
    try:
        return get_filing_aggregates(from_, to, form, q)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"EDGAR unavailable: {e}")


@router.get("/dataset-bounds")
def dataset_bounds():
    return {"from": "1993-01-01", "to": "2025-12-31"}
