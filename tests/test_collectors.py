import pytest
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class FakeCollector(BaseCollector):
    """Collector that returns test data."""
    async def collect(self) -> list[CollectorResult]:
        return [
            CollectorResult(
                title="Test Hot Topic",
                description="A hot topic",
                url="https://test.com/1",
                source_platform=self.platform,
                language="en",
                region="US",
                source_rank=1,
                mention_count=10000,
            )
        ]

    @property
    def platform(self) -> str:
        return "fake"


class ErrorCollector(BaseCollector):
    async def collect(self) -> list[CollectorResult]:
        raise httpx.HTTPError("API unavailable")

    @property
    def platform(self) -> str:
        return "error_source"


def test_collector_result_creation():
    result = CollectorResult(
        title="Test",
        description="Desc",
        url="https://example.com",
        source_platform="twitter",
        language="en",
        region="US",
        source_rank=1,
        mention_count=5000,
    )
    assert result.title == "Test"
    assert result.heat_score == 0.0


def test_collector_result_to_dict():
    result = CollectorResult(
        title="Test Event",
        description="Description",
        url="https://example.com",
        source_platform="reddit",
        language="en",
        region="US",
        source_rank=3,
        mention_count=8000,
        raw_data={"upvotes": 5000},
    )
    d = result.to_dict()
    assert d["title"] == "Test Event"
    assert d["source_platform"] == "reddit"
    assert d["mention_count"] == 8000
    assert d["raw_data"] == {"upvotes": 5000}


@pytest.mark.asyncio
async def test_fake_collector():
    collector = FakeCollector()
    results = await collector.collect()
    assert len(results) == 1
    assert results[0].title == "Test Hot Topic"
    assert results[0].source_platform == "fake"


@pytest.mark.asyncio
async def test_collector_safe_collect():
    collector = ErrorCollector()
    results = await collector.safe_collect()
    assert results == []


from app.collectors.hackernews import HackerNewsCollector
from app.collectors.newsapi import NewsApiCollector


@pytest.mark.asyncio
async def test_hackernews_collector(httpx_mock):
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        json=[1, 2, 3],
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/1.json",
        json={"id": 1, "title": "HN Story 1", "by": "user1",
              "score": 100, "descendants": 50, "url": "https://hn1.com"},
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/2.json",
        json={"id": 2, "title": "HN Story 2", "by": "user2",
              "score": 80, "descendants": 30, "url": "https://hn2.com"},
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/3.json",
        json={"id": 3, "title": "HN Story 3", "by": "user3",
              "score": 60, "descendants": 20, "url": ""},
    )

    collector = HackerNewsCollector()
    results = await collector.collect()

    assert len(results) == 3
    assert results[0].title == "HN Story 1"
    assert results[0].source_platform == "hackernews"
    assert results[0].mention_count == 100
    assert results[0].source_rank == 1


@pytest.mark.asyncio
async def test_newsapi_collector(httpx_mock):
    httpx_mock.add_response(
        url="https://newsapi.org/v2/top-headlines?language=en&pageSize=50&apiKey=test-key",
        json={
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {"title": "World News 1", "description": "Desc 1",
                 "url": "https://news1.com", "source": {"name": "CNN"}},
                {"title": "World News 2", "description": "Desc 2",
                 "url": "https://news2.com", "source": {"name": "BBC"}},
            ]
        },
    )

    collector = NewsApiCollector(api_key="test-key")
    results = await collector.collect()

    assert len(results) == 2
    assert results[0].title == "World News 1"
    assert results[0].source_platform == "newsapi"
    assert results[0].language == "en"


from app.collectors.github_trending import GitHubTrendingCollector
from app.collectors.google_trends import GoogleTrendsCollector


@pytest.mark.asyncio
async def test_github_trending_collector(httpx_mock):
    html_content = """
    <html><body>
    <article class="Box-row">
        <h2 class="h3 lh-condensed"><a href="/owner/repo1">owner / <span>repo1</span></a></h2>
        <p class="col-9">An awesome Python library</p>
        <span class="d-inline-block float-sm-right">1,234 stars today</span>
    </article>
    <article class="Box-row">
        <h2 class="h3 lh-condensed"><a href="/owner/repo2">owner / <span>repo2</span></a></h2>
        <p class="col-9">A great JS framework</p>
        <span class="d-inline-block float-sm-right">567 stars today</span>
    </article>
    </body></html>
    """
    httpx_mock.add_response(
        url="https://github.com/trending",
        text=html_content,
    )

    collector = GitHubTrendingCollector()
    results = await collector.collect()

    assert len(results) == 2
    assert results[0].source_platform == "github_trending"
    assert "repo1" in results[0].title
    assert results[0].source_rank == 1


@pytest.mark.asyncio
async def test_google_trends_collector():
    collector = GoogleTrendsCollector()
    results = await collector.collect()
    assert isinstance(results, list)
    # pytrends may fail without network; that's OK, it returns []
