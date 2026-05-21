import httpx
from bs4 import BeautifulSoup
from app.collectors.base import BaseCollector, CollectorResult


class GitHubTrendingCollector(BaseCollector):
    URL = "https://github.com/trending"

    @property
    def platform(self) -> str:
        return "github_trending"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(self.URL)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        articles = soup.find_all("article", class_="Box-row")[:25]
        for rank, article in enumerate(articles, 1):
            h2 = article.find("h2")
            if not h2:
                continue
            link = h2.find("a")
            repo_name = link.text.strip().replace("\n", "").replace(" ", "") if link else ""
            desc_el = article.find("p", class_="col-9")
            description = desc_el.text.strip() if desc_el else ""
            stars_el = article.find("span", class_="float-sm-right")
            stars_text = stars_el.text.strip() if stars_el else "0"
            mention_count = int("".join(c for c in stars_text if c.isdigit()) or 0)

            results.append(CollectorResult(
                title=f"{repo_name}",
                description=description,
                url=f"https://github.com{link['href']}" if link and link.get("href") else "",
                source_platform=self.platform,
                language="en",
                region="US",
                source_rank=rank,
                mention_count=mention_count,
                raw_data={"stars_today": stars_text},
            ))
        return results
