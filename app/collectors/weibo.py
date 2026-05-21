import httpx
from app.collectors.base import BaseCollector, CollectorResult


class WeiboCollector(BaseCollector):
    URL = "https://weibo.com/ajax/side/hotSearch"

    @property
    def platform(self) -> str:
        return "weibo"

    @property
    def interval_minutes(self) -> int:
        return 10

    async def collect(self) -> list[CollectorResult]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        items = data.get("data", {}).get("realtime", [])[:50]
        for rank, item in enumerate(items, 1):
            word = item.get("word", "") or item.get("note", "")
            if not word:
                continue
            results.append(CollectorResult(
                title=word,
                description=f"热度: {item.get('num', 0)}",
                url=f"https://s.weibo.com/weibo?q={word}",
                source_platform=self.platform,
                language="zh",
                region="CN",
                source_rank=rank,
                mention_count=item.get("num", 0) or item.get("raw_hot", 0),
                raw_data=item,
            ))
        return results
