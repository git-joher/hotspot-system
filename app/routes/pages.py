from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.i18n import get_lang, t as translate, get_bilingual_data
from app.seo import (
    truncate,
    build_canonical_url,
    build_website_schema,
    build_newsarticle_schema,
    iso_to_rfc2822,
)
from app.database import get_db, get_event_with_snapshots, get_events_by_timespan
from config import SITE_URL

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.filters["rfc2822"] = iso_to_rfc2822


def _ctx(request: Request, extra: dict = None) -> dict:
    lang = get_lang(request)
    name = translate(lang, "app_name")
    desc = translate(lang, "site_description")
    keywords = translate(lang, "site_keywords")
    site = SITE_URL.rstrip("/")
    ctx = {
        "lang": lang,
        "t": lambda key: translate(lang, key),
        "i18n_data": get_bilingual_data(),
        "base_path": "/",
        "meta_description": desc,
        "meta_keywords": keywords,
        "og_title": name,
        "og_description": desc,
        "og_type": "website",
        "og_url": site,
        "og_locale": "zh_CN" if lang == "zh" else "en_US",
        "canonical_url": site,
        "website_schema": build_website_schema(SITE_URL, lang, name, desc),
    }
    if extra:
        ctx.update(extra)
    return ctx


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _ctx(request))


@router.get("/event/{event_id}", response_class=HTMLResponse)
async def event_detail(request: Request, event_id: int):
    lang = get_lang(request)
    conn = get_db()
    try:
        data = get_event_with_snapshots(conn, event_id)
        event = data["event"] if data else None
    finally:
        conn.close()

    extra: dict = {"event_id": event_id}

    if event:
        title = event.get(f"title_{lang}") or event.get("title", "")
        desc = event.get(f"summary_{lang}") or event.get("description", "")
        desc_truncated = truncate(desc, 200)
        event_url = build_canonical_url(SITE_URL, f"/event/{event_id}")
        extra.update({
            "meta_title": title or translate(lang, "app_name"),
            "meta_description": desc_truncated or translate(lang, "site_description"),
            "og_title": title or translate(lang, "app_name"),
            "og_description": desc_truncated or translate(lang, "site_description"),
            "og_type": "article",
            "og_url": event_url,
            "canonical_url": event_url,
            "newsarticle_schema": build_newsarticle_schema(event, SITE_URL, lang),
            "share_url": event_url,
        })

    return templates.TemplateResponse(request, "detail.html", _ctx(request, extra))


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    site = SITE_URL.rstrip("/")
    return f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n"


@router.get("/sitemap.xml")
async def sitemap(request: Request):
    conn = get_db()
    try:
        events = get_events_by_timespan(conn, hours=720, limit=5000)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "sitemap.xml", {
        "request": request,
        "site_url": SITE_URL.rstrip("/"),
        "events": events,
    }, media_type="application/xml")


@router.get("/rss")
async def rss(request: Request):
    lang = get_lang(request)
    conn = get_db()
    try:
        events = get_events_by_timespan(conn, hours=24, limit=50)
    finally:
        conn.close()
    name = translate(lang, "app_name")
    desc = translate(lang, "site_description")
    return templates.TemplateResponse(request, "rss.xml", {
        "request": request,
        "site_url": SITE_URL.rstrip("/"),
        "name": name,
        "description": desc,
        "lang": lang,
        "events": events,
    }, media_type="application/xml")
