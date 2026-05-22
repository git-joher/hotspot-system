import asyncio
import feedparser
import httpx
from app.collectors.base import BaseCollector, CollectorResult


DEFAULT_CN_FEEDS = [
    # Financial news
    ("https://feedx.net/rss/sinafinance.xml", "zh", "CN"),
    ("https://feedx.net/rss/eastmoney.xml", "zh", "CN"),
    ("https://feedx.net/rss/cls.xml", "zh", "CN"),
    # Government & policy
    ("http://www.people.com.cn/rss/politics.xml", "zh", "CN"),
    ("http://www.xinhuanet.com/politics/xhll.xml", "zh", "CN"),
    # Securities & regulatory
    ("https://feedx.net/rss/stcn.xml", "zh", "CN"),
    ("https://feedx.net/rss/yicai.xml", "zh", "CN"),
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
