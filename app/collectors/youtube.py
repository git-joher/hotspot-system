import httpx
from app.collectors.base import BaseCollector, CollectorResult


class YouTubeCollector(BaseCollector):
    BASE_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def platform(self) -> str:
        return "youtube"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        if not self.api_key:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.BASE_URL,
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": "US",
                    "maxResults": 50,
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for rank, item in enumerate(data.get("items", []), 1):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                results.append(CollectorResult(
                    title=snippet.get("title", ""),
                    description=snippet.get("description", "")[:300],
                    url=f"https://youtube.com/watch?v={item.get('id', '')}",
                    source_platform=self.platform,
                    language=snippet.get("defaultAudioLanguage", "unknown"),
                    region=snippet.get("country", "US"),
                    source_rank=rank,
                    mention_count=int(stats.get("viewCount", 0)),
                    raw_data=item,
                ))
            return results
