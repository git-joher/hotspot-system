from app.collectors.base import BaseCollector, CollectorResult


class GoogleTrendsCollector(BaseCollector):
    @property
    def platform(self) -> str:
        return "google_trends"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)
            data = pytrends.trending_searches(pn="united_states")
            results = []
            for rank, row in enumerate(data.head(50).itertuples(), 1):
                results.append(CollectorResult(
                    title=row[1] if len(row) > 1 else str(row),
                    source_platform=self.platform,
                    language="en",
                    region="US",
                    source_rank=rank,
                    mention_count=0,
                ))
            return results
        except Exception:
            return []
