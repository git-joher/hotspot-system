import httpx
from app.collectors.base import BaseCollector, CollectorResult


class TwitterCollector(BaseCollector):
    WOEID_GLOBAL = 1

    def __init__(self, bearer_token: str = ""):
        self.bearer_token = bearer_token

    @property
    def platform(self) -> str:
        return "twitter"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        if not self.bearer_token:
            return []

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.twitter.com/1.1/trends/place.json",
                params={"id": self.WOEID_GLOBAL},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for trend_data in data:
                for rank, trend in enumerate(trend_data.get("trends", [])[:50], 1):
                    results.append(CollectorResult(
                        title=trend.get("name", ""),
                        description=f"Tweet volume: {trend.get('tweet_volume', 0) or 'N/A'}",
                        url=trend.get("url", ""),
                        source_platform=self.platform,
                        language="en",
                        region="global",
                        source_rank=rank,
                        mention_count=trend.get("tweet_volume") or 0,
                        raw_data=trend,
                    ))
            return results
