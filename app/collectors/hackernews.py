import httpx
from app.collectors.base import BaseCollector, CollectorResult


class HackerNewsCollector(BaseCollector):
    TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

    @property
    def platform(self) -> str:
        return "hackernews"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.TOP_STORIES_URL)
            resp.raise_for_status()
            story_ids = resp.json()[:50]

            results = []
            for rank, sid in enumerate(story_ids, 1):
                try:
                    item_resp = await client.get(self.ITEM_URL.format(sid))
                    item_resp.raise_for_status()
                    item = item_resp.json()
                    if item and item.get("title"):
                        results.append(CollectorResult(
                            title=item.get("title", ""),
                            description=f"By {item.get('by', 'unknown')}",
                            url=item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                            source_platform=self.platform,
                            language="en",
                            region="US",
                            source_rank=rank,
                            mention_count=item.get("score", 0),
                            raw_data=item,
                        ))
                except Exception:
                    continue
            return results
