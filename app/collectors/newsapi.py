import httpx
from app.collectors.base import BaseCollector, CollectorResult


class NewsApiCollector(BaseCollector):
    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def platform(self) -> str:
        return "newsapi"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        if not self.api_key:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.BASE_URL,
                params={"language": "en", "pageSize": 50, "apiKey": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for rank, article in enumerate(data.get("articles", [])[:50], 1):
                if article.get("title"):
                    results.append(CollectorResult(
                        title=article["title"],
                        description=article.get("description", ""),
                        url=article.get("url", ""),
                        source_platform=self.platform,
                        language="en",
                        region=article.get("source", {}).get("name", "US"),
                        source_rank=rank,
                        mention_count=0,
                        raw_data=article,
                    ))
            return results
