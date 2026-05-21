import asyncio
import feedparser
import httpx
from app.collectors.base import BaseCollector, CollectorResult


DEFAULT_RSS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "en", "GB"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en", "US"),
    ("https://www3.nhk.or.jp/rss/news/cat6.xml", "ja", "JP"),
]


class RSSCollector(BaseCollector):
    def __init__(self, feeds: list = None):
        self.feeds = feeds or DEFAULT_RSS_FEEDS

    @property
    def platform(self) -> str:
        return "rss"

    @property
    def interval_minutes(self) -> int:
        return 30

    async def collect(self) -> list[CollectorResult]:
        results = []
        loop = asyncio.get_event_loop()

        for feed_url, lang, region in self.feeds:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
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
