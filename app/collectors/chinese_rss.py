import asyncio
import feedparser
import httpx
from app.collectors.base import BaseCollector, CollectorResult


DEFAULT_CN_FEEDS = [
    # People's Daily — authoritative government/party voice
    ("http://www.people.com.cn/rss/politics.xml", "zh", "CN"),      # 人民日报-政治
    ("http://www.people.com.cn/rss/finance.xml", "zh", "CN"),       # 人民日报-财经
    ("http://www.people.com.cn/rss/world.xml", "zh", "CN"),         # 人民日报-国际
    # China News Service — official state news agency
    ("https://www.chinanews.com.cn/rss/scroll-news.xml", "zh", "CN"),    # 中国新闻网-要闻
    ("https://www.chinanews.com.cn/rss/finance.xml", "zh", "CN"),        # 中国新闻网-财经
]


class ChineseRSSCollector(BaseCollector):
    def __init__(self, feeds: list = None):
        self.feeds = feeds or DEFAULT_CN_FEEDS

    @property
    def platform(self) -> str:
        return "chinese_rss"

    @property
    def interval_minutes(self) -> int:
        return 30

    async def collect(self) -> list[CollectorResult]:
        results = []
        loop = asyncio.get_event_loop()

        for feed_url, lang, region in self.feeds:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                    feed = await loop.run_in_executor(
                        None, feedparser.parse, resp.text
                    )

                for rank, entry in enumerate(feed.entries[:20], 1):
                    results.append(CollectorResult(
                        title=entry.get("title", ""),
                        description=entry.get("summary", "")[:300],
                        url=entry.get("link", ""),
                        source_platform=self.platform,
                        language=lang,
                        region=region,
                        source_rank=rank,
                        mention_count=0,
                        raw_data={"published": entry.get("published", "")},
                    ))
            except Exception:
                continue

        return results
