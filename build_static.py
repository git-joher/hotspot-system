"""
Static site builder for Hotspot system.
Run this locally to rebuild the entire static site in docs/.

Usage:
    python build_static.py            # full build: collect + process + export
    python build_static.py --skip-collect  # export only (skip collecting fresh data)
"""
import argparse
import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path

import dotenv

dotenv.load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import (
    DATA_DIR,
    SITE_URL,
    NEWSAPI_KEY,
    TWITTER_BEARER_TOKEN,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    YOUTUBE_API_KEY,
)
from app.database import (
    get_db,
    init_db,
    get_events_by_timespan,
    get_entity_aggregates,
    get_predictions,
    get_stats,
    get_event_with_snapshots,
)
from app.i18n import TRANSLATIONS, get_bilingual_data, t as translate
from app.seo import (
    truncate,
    build_canonical_url,
    build_website_schema,
    build_newsarticle_schema,
    iso_to_rfc2822,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATE_DIR = BASE_DIR / "app" / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)
_jinja_env.filters["rfc2822"] = iso_to_rfc2822


def _make_collectors():
    from app.collectors.hackernews import HackerNewsCollector
    from app.collectors.github_trending import GitHubTrendingCollector
    from app.collectors.weibo import WeiboCollector
    from app.collectors.zhihu import ZhihuCollector
    from app.collectors.baidu import BaiduCollector
    from app.collectors.chinese_rss import ChineseRSSCollector
    from app.collectors.newsapi import NewsApiCollector
    from app.collectors.reddit import RedditCollector
    from app.collectors.twitter import TwitterCollector
    from app.collectors.youtube import YouTubeCollector
    from app.collectors.google_trends import GoogleTrendsCollector
    from app.collectors.rss_feeds import RSSCollector

    return [
        HackerNewsCollector(),
        GitHubTrendingCollector(),
        WeiboCollector(),
        ZhihuCollector(),
        BaiduCollector(),
        ChineseRSSCollector(),
        NewsApiCollector(api_key=NEWSAPI_KEY),
        RedditCollector(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET),
        TwitterCollector(bearer_token=TWITTER_BEARER_TOKEN),
        YouTubeCollector(api_key=YOUTUBE_API_KEY),
        GoogleTrendsCollector(),
        RSSCollector(),
    ]


def ensure_dirs():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "data").mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "event").mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "static").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1: Collect & process
# ---------------------------------------------------------------------------
async def collect_and_process():
    from app.pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    collectors = _make_collectors()

    logger.info("Starting collection from %d platforms...", len(collectors))
    all_results = []
    for collector in collectors:
        try:
            logger.info("  %s ...", collector.platform)
            results = await collector.safe_collect()
            all_results.extend(results)
            logger.info("  %s: %d items", collector.platform, len(results))
        except Exception as e:
            logger.error("  %s error: %s", collector.platform, e)

    if not all_results:
        logger.warning("No results collected!")
        return

    conn = get_db()
    try:
        init_db(conn)
        new_count = await orchestrator.run(all_results, conn)
        logger.info("Pipeline complete: %d new events from %d raw items", new_count, len(all_results))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Step 2: Export data from DB
# ---------------------------------------------------------------------------
def export_data():
    conn = get_db()
    try:
        events = get_events_by_timespan(conn, hours=720, limit=500)
        entities = get_entity_aggregates(conn, hours=720)
        predictions = get_predictions(conn)
        stats = get_stats(conn)
        cn_stats = get_stats(conn, region="CN")

        top5 = get_events_by_timespan(conn, hours=720, limit=5, sort_by="heat")
        top5_snapshots = {}
        for e in top5:
            data = get_event_with_snapshots(conn, e["id"])
            if data and data["snapshots"]:
                top5_snapshots[str(e["id"])] = data["snapshots"]

        return events, entities, predictions, stats, cn_stats, top5_snapshots
    finally:
        conn.close()


def _json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, default=str)


def write_json_files(events, entities, predictions, stats, top5_snapshots):
    data_dir = DOCS_DIR / "data"
    (data_dir / "all_events.json").write_text(_json_dumps(events), encoding="utf-8")
    (data_dir / "entities.json").write_text(_json_dumps(entities), encoding="utf-8")
    (data_dir / "predictions.json").write_text(_json_dumps(predictions), encoding="utf-8")
    (data_dir / "stats.json").write_text(_json_dumps(stats), encoding="utf-8")
    (data_dir / "snapshots_top5.json").write_text(_json_dumps(top5_snapshots), encoding="utf-8")
    (data_dir / "i18n.json").write_text(_json_dumps(get_bilingual_data()), encoding="utf-8")
    logger.info("JSON data files written to docs/data/")


# ---------------------------------------------------------------------------
# Step 3: Build HTML pages (Jinja2 offline rendering)
# ---------------------------------------------------------------------------
def _render(template_name, context, rel_path):
    template = _jinja_env.get_template(template_name)
    out = DOCS_DIR / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.render(**context), encoding="utf-8")


def _base_path():
    """Extract path prefix from SITE_URL for subpath deployments."""
    from urllib.parse import urlparse
    path = urlparse(SITE_URL).path.rstrip("/")
    return path + "/" if path else "/"


def _seo_ctx(lang="en"):
    name = translate(lang, "app_name")
    desc = translate(lang, "site_description")
    keywords = translate(lang, "site_keywords")
    site = SITE_URL.rstrip("/")
    return {
        "lang": lang,
        "t": lambda key: translate(lang, key),
        "i18n_data": get_bilingual_data(),
        "base_path": _base_path(),
        "meta_title": name,
        "meta_description": desc,
        "meta_keywords": keywords,
        "og_title": name,
        "og_description": desc,
        "og_type": "website",
        "og_url": site,
        "og_locale": "en_US",
        "canonical_url": site,
        "website_schema": build_website_schema(SITE_URL, lang, name, desc),
    }


def _event_seo_ctx(event, lang="en"):
    ctx = _seo_ctx(lang)
    title = event.get(f"title_{lang}") or event.get("title", "")
    desc = event.get(f"summary_{lang}") or event.get("description", "")
    desc_trunc = truncate(desc, 200)
    eid = event["id"]
    ev_url = build_canonical_url(SITE_URL, f"/event/{eid}")
    ctx.update({
        "meta_title": title or translate(lang, "app_name"),
        "meta_description": desc_trunc or translate(lang, "site_description"),
        "og_title": title or translate(lang, "app_name"),
        "og_description": desc_trunc or translate(lang, "site_description"),
        "og_type": "article",
        "og_url": ev_url,
        "canonical_url": ev_url,
        "newsarticle_schema": build_newsarticle_schema(event, SITE_URL, lang),
        "share_url": ev_url,
    })
    return ctx


def build_index(events, entities, predictions, stats, cn_stats, top5_snapshots):
    ctx = _seo_ctx("en")
    ctx.update({
        "is_static": True,
        "event_id": None,
        "events_json": _json_dumps(events),
        "entities_json": _json_dumps(entities),
        "predictions_json": _json_dumps(predictions),
        "stats_json": _json_dumps(stats),
        "cn_stats_json": _json_dumps(cn_stats),
        "snapshots_top5_json": _json_dumps(top5_snapshots),
    })
    _render("index.html", ctx, "index.html")
    logger.info("Built index.html")


def build_event_pages(events):
    conn = get_db()
    try:
        count = 0
        for event in events[:500]:
            eid = event["id"]
            data = get_event_with_snapshots(conn, eid)
            if not data:
                continue
            ctx = _event_seo_ctx(data["event"], "en")
            ctx["is_static"] = True
            ctx["event_id"] = eid
            ctx["event_json"] = _json_dumps(data)
            _render("detail.html", ctx, f"event/{eid}.html")
            count += 1
    finally:
        conn.close()
    logger.info("Built %d event detail pages", count)


# ---------------------------------------------------------------------------
# Step 4: Generate XML / txt files
# ---------------------------------------------------------------------------
def generate_xml_files(events):
    site = SITE_URL.rstrip("/")
    (DOCS_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n",
        encoding="utf-8",
    )
    _render("sitemap.xml", {"site_url": site, "events": events[:500]}, "sitemap.xml")
    _render("rss.xml", {
        "site_url": site,
        "name": translate("en", "app_name"),
        "description": translate("en", "site_description"),
        "lang": "en",
        "events": events[:50],
    }, "rss.xml")
    logger.info("Generated robots.txt, sitemap.xml, rss.xml")


# ---------------------------------------------------------------------------
# Step 5: Copy static assets
# ---------------------------------------------------------------------------
def copy_static():
    dest = DOCS_DIR / "static"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(str(STATIC_DIR), str(dest))
    # Also copy the modified JS files (they're already in STATIC_DIR since we edit in place)
    logger.info("Copied static assets to docs/static/")


def write_cname(domain=None):
    if domain:
        (DOCS_DIR / "CNAME").write_text(domain.strip(), encoding="utf-8")
        logger.info("Wrote CNAME: %s", domain)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(skip_collect=False):
    ensure_dirs()

    if not skip_collect:
        await collect_and_process()

    events, entities, predictions, stats, cn_stats, top5_snapshots = export_data()
    logger.info(
        "Exported: %d events, %d entities, %d predictions",
        len(events), len(entities), len(predictions),
    )

    write_json_files(events, entities, predictions, stats, top5_snapshots)
    build_index(events, entities, predictions, stats, cn_stats, top5_snapshots)
    build_event_pages(events)
    generate_xml_files(events)
    copy_static()

    # Uncomment and set your domain:
    # write_cname("hotspot.example.com")

    logger.info("=" * 50)
    logger.info("Build complete! Site is in docs/")
    logger.info("  Preview: cd docs && python -m http.server 8080")
    logger.info("  Deploy:  git add docs/ && git commit -m 'rebuild site' && git push")
    logger.info("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build static Hotspot site")
    parser.add_argument("--skip-collect", action="store_true", help="Skip data collection, export from existing DB")
    args = parser.parse_args()
    asyncio.run(main(skip_collect=args.skip_collect))
