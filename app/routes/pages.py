from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.i18n import get_lang, t as translate, get_bilingual_data

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _ctx(request: Request, extra: dict = None) -> dict:
    lang = get_lang(request)
    ctx = {
        "lang": lang,
        "t": lambda key: translate(lang, key),
        "i18n_data": get_bilingual_data(),
    }
    if extra:
        ctx.update(extra)
    return ctx


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _ctx(request))


@router.get("/event/{event_id}", response_class=HTMLResponse)
async def event_detail(request: Request, event_id: int):
    return templates.TemplateResponse(request, "detail.html", _ctx(request, {"event_id": event_id}))
