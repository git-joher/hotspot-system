import httpx
from app.collectors.base import BaseCollector, CollectorResult


class RedditCollector(BaseCollector):
    BASE_URL = "https://www.reddit.com/r/all/hot.json"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def platform(self) -> str:
        return "reddit"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        headers = {"User-Agent": "HotspotAggregator/1.0"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.BASE_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            results = []
            posts = data.get("data", {}).get("children", [])[:50]
            for rank, child in enumerate(posts, 1):
                post = child["data"]
                results.append(CollectorResult(
                    title=post.get("title", ""),
                    description=post.get("selftext", "")[:300],
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    source_platform=self.platform,
                    language="en",
                    region=post.get("subreddit", "unknown"),
                    source_rank=rank,
                    mention_count=post.get("score", 0) + post.get("num_comments", 0),
                    raw_data=post,
                ))
            return results
