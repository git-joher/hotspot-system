import httpx
from app.collectors.base import BaseCollector, CollectorResult


class ZhihuCollector(BaseCollector):
    URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"

    @property
    def platform(self) -> str:
        return "zhihu"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("data", [])[:50]:
            target = item.get("target", {})
            title = target.get("title", "")
            if not title:
                continue
            results.append(CollectorResult(
                title=title,
                description=target.get("excerpt", "")[:300],
                url=target.get("url", f"https://www.zhihu.com/question/{target.get('id', '')}"),
                source_platform=self.platform,
                language="zh",
                region="CN",
                source_rank=item.get("position", 1),
                mention_count=int(target.get("follower_count", 0) or 0),
                raw_data=item,
            ))
        return results
