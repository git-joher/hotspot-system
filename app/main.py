import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import get_db, init_db, cleanup_old_snapshots, cleanup_old_predictions
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
from app.pipeline.orchestrator import PipelineOrchestrator
from app.routes.pages import router as pages_router
from app.routes.api import router as api_router
from config import (
    TWITTER_BEARER_TOKEN, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    YOUTUBE_API_KEY, NEWSAPI_KEY,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
orchestrator = PipelineOrchestrator()
collection_lock = threading.Lock()

collectors = [
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


async def run_all_collectors():
    if not collection_lock.acquire(blocking=False):
        logger.info("Collection already running, skipping this cycle")
        return

    try:
        all_results = []
        for collector in collectors:
            try:
                logger.info(f"Collecting from {collector.platform}...")
                results = await collector.safe_collect()
                all_results.extend(results)
                logger.info(f"  {collector.platform}: {len(results)} items")
            except Exception as e:
                logger.error(f"Collector {collector.platform} error: {e}")

        if all_results:
            conn = get_db()
            try:
                new_count = await orchestrator.run(all_results, conn)
                logger.info(f"Pipeline complete: {new_count} new events from {len(all_results)} raw items")
            except Exception as e:
                logger.error(f"Pipeline error: {e}", exc_info=True)
            finally:
                conn.close()
    finally:
        collection_lock.release()


def scheduled_collection():
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_all_collectors())
    except Exception as e:
        logger.error(f"Scheduled collection failed: {e}", exc_info=True)
    finally:
        loop.close()


def daily_cleanup():
    conn = get_db()
    try:
        removed_snaps = cleanup_old_snapshots(conn)
        removed_preds = cleanup_old_predictions(conn)
        logger.info(f"Cleanup: removed {removed_snaps} old snapshots, {removed_preds} expired predictions")
    finally:
        conn.close()


def daily_prediction_refresh():
    import asyncio
    async def _run():
        conn = get_db()
        try:
            from app.database import get_events_by_timespan, get_entity_aggregates, replace_predictions, get_predictions
            events = get_events_by_timespan(conn, hours=24, limit=50, sort_by="heat")
            entities = get_entity_aggregates(conn, hours=24)
            if events:
                predictions = await orchestrator.llm.predict_opportunities(events, entities)
                if predictions:
                    replace_predictions(conn, predictions)
                    logger.info(f"Prediction refresh: {len(predictions)} predictions stored")
        except Exception as e:
            logger.error(f"Prediction refresh failed: {e}")
        finally:
            conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_db()
    init_db(conn)
    conn.close()

    app.state.db = get_db()
    logger.info("Database initialized")

    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_collection, 'interval', minutes=30, id='collect')
    scheduler.add_job(daily_cleanup, 'interval', hours=24, id='cleanup')
    scheduler.add_job(daily_prediction_refresh, 'interval', hours=6, id='prediction_refresh')
    scheduler.start()
    logger.info("Scheduler started (collection every 30 min, predictions every 6h)")

    app.state.scheduler = scheduler

    yield

    if hasattr(app.state, 'db') and app.state.db:
        app.state.db.close()

    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(title="Hotspot - 全球热点雷达", lifespan=lifespan)

static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(pages_router)
app.include_router(api_router)
