import httpx
from app.collectors.base import BaseCollector, CollectorResult


class BaiduCollector(BaseCollector):
    URL = "https://top.baidu.com/board?tab=realtime"

    @property
    def platform(self) -> str:
        return "baidu"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(self.URL, headers=headers)
            resp.raise_for_status()
            api_resp = await client.get(
                "https://top.baidu.com/api/board?platform=wise&tab=realtime",
                headers=headers,
            )
            api_resp.raise_for_status()
            data = api_resp.json()

        results = []
        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            for item in card.get("content", [])[:50]:
                word = item.get("word", "") or item.get("query", "")
                if not word:
                    continue
                results.append(CollectorResult(
                    title=word,
                    description=item.get("desc", ""),
                    url=item.get("url", ""),
                    source_platform=self.platform,
                    language="zh",
                    region="CN",
                    source_rank=item.get("index", 1),
                    mention_count=item.get("hotScore", 0) or item.get("heat_score", 0),
                    raw_data=item,
                ))
        return results
