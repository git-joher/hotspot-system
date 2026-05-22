from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from app.database import (get_db, get_events_by_timespan, get_event_with_snapshots,
                          get_stats, search_events, get_entity_aggregates,
                          replace_predictions, get_predictions)

router = APIRouter(prefix="/api", tags=["api"])


def _get_conn(request: Request):
    conn = getattr(request.app.state, "db", None)
    if conn is None:
        from app.database import get_db
        conn = get_db()
        request.app.state.db = conn
    return conn


@router.get("/events")
async def api_events(
    request: Request,
    timespan: str = Query("realtime"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: str = Query(None),
    source: str = Query(None),
    region: str = Query(None),
    sort_by: str = Query("heat"),
):
    timespan_map = {"realtime": 1, "hourly": 3, "daily": 24}
    hours = timespan_map.get(timespan, 1)

    conn = _get_conn(request)
    events = get_events_by_timespan(
        conn, hours=hours, limit=limit, offset=offset,
        category_slug=category, source_platform=source, region=region, sort_by=sort_by,
    )
    return {"events": events, "timespan": timespan, "hours": hours}


@router.get("/events/{event_id}")
async def api_event_detail(request: Request, event_id: int):
    conn = _get_conn(request)
    result = get_event_with_snapshots(conn, event_id)
    if result is None:
        return {"error": "Event not found"}
    return result


@router.get("/stats")
async def api_stats(request: Request, region: str = Query(None)):
    conn = _get_conn(request)
    return get_stats(conn, region=region)


@router.get("/categories")
async def api_categories(request: Request):
    conn = _get_conn(request)
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@router.get("/search")
async def api_search(request: Request, q: str = Query(..., min_length=1), limit: int = Query(50)):
    conn = _get_conn(request)
    return {"results": search_events(conn, q, limit)}


@router.get("/entities")
async def api_entities(
    request: Request,
    timespan: str = Query("realtime"),
    region: str = Query(None),
):
    timespan_map = {"realtime": 1, "hourly": 3, "daily": 24}
    hours = timespan_map.get(timespan, 1)
    conn = _get_conn(request)
    entities = get_entity_aggregates(conn, hours=hours, region=region)
    return {"entities": entities, "timespan": timespan}


@router.post("/refresh")
async def api_refresh(request: Request):
    from app.main import scheduled_collection
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, scheduled_collection)
    return {"status": "ok", "message": "Collection triggered"}


@router.get("/predictions")
async def api_get_predictions(request: Request, region: str = Query(None)):
    conn = _get_conn(request)
    predictions = get_predictions(conn)
    # Predictions don't have a region column; filtering happens at refresh time
    # When region=CN, return all predictions (they were CN-focused if refreshed with CN events)
    return {"predictions": predictions}


@router.post("/predictions/refresh")
async def api_refresh_predictions(request: Request, region: str = Query(None)):
    from app.database import get_db as _get_db
    conn = _get_db()
    try:
        events = get_events_by_timespan(conn, hours=24, limit=50, sort_by="heat", region=region)
        entities = get_entity_aggregates(conn, hours=24, region=region)

        from app.pipeline.llm_processor import LLMProcessor
        llm = LLMProcessor()
        predictions = await llm.predict_opportunities(events, entities, region=region)
        if predictions:
            replace_predictions(conn, predictions)
            return {"status": "ok", "count": len(predictions), "predictions": get_predictions(conn)}
        return {"status": "empty", "count": 0, "predictions": []}
    finally:
        conn.close()


@router.post("/lang/{lang}")
async def api_set_lang(lang: str):
    if lang not in ("zh", "en"):
        return JSONResponse({"status": "error", "message": "Invalid language"}, status_code=400)
    resp = JSONResponse({"status": "ok", "lang": lang})
    resp.set_cookie("lang", lang, max_age=365 * 24 * 3600)
    return resp
