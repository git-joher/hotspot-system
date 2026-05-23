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
            card_content = card.get("content", [])
            for item in card_content:
                # Handle nested structure: wrapper dict with inner 'content' list
                if isinstance(item, dict) and "content" in item and isinstance(item["content"], list):
                    inner_items = item["content"]
                elif isinstance(item, dict) and "word" in item:
                    inner_items = [item]
                else:
                    continue

                rank = 0
                for inner in inner_items:
                    rank += 1
                    word = inner.get("word", "") or inner.get("query", "")
                    if not word:
                        continue
                    # Extract hot score from hotTag or hotScore
                    hot_str = inner.get("hotTag", "") or inner.get("hotScore", "")
                    try:
                        hot_score = int(hot_str) if hot_str else 0
                    except (ValueError, TypeError):
                        hot_score = 0
                    results.append(CollectorResult(
                        title=word,
                        description=inner.get("desc", ""),
                        url=inner.get("url", ""),
                        source_platform=self.platform,
                        language="zh",
                        region="CN",
                        source_rank=inner.get("index", rank),
                        mention_count=hot_score,
                        raw_data=inner,
                    ))
        return results
