from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import httpx
from models import RawItem, SourceType
from collectors.base import BaseCollector


class GitHubCollector(BaseCollector):
    BASE_URL = "https://api.github.com"

    def __init__(self, config: dict):
        super().__init__(config)
        token = self.config.get("token", "")
        self.headers = {
            "Accept": "application/vnd.github+3+json",
        }
        if token and not token.startswith("${"):
            self.headers["Authorization"] = f"Bearer {token}"

    @property
    def source_name(self) -> str:
        return "github"

    async def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        tasks = []
        keywords = self.config.get("keywords", [])
        for kw in keywords[:10]:
            tasks.append(self._search_repos(kw))
        for repo in self.config.get("watch_repos", []):
            tasks.append(self._get_repo_releases(repo))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        seen_urls: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                continue
            for item in result:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:30]

    async def _search_repos(self, keyword: str) -> list[RawItem]:
        since = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%d")
        params = {
            "q": f"{keyword} pushed:>{since}",
            "sort": "stars",
            "order": "desc",
            "per_page": 5,
        }
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(f"{self.BASE_URL}/search/repositories", params=params)
            resp.raise_for_status()
            data = resp.json()
        items = []
        for repo in data.get("items", []):
            items.append(RawItem(
                title=repo["full_name"],
                url=repo["html_url"],
                source_type=SourceType.GITHUB,
                content=repo.get("description", "") or "",
                published_at=datetime.strptime(
                    repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc),
                extra={
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "description": repo.get("description", ""),
                },
            ))
        return items

    async def _get_repo_releases(self, repo_full: str) -> list[RawItem]:
        params = {"per_page": 5}
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{repo_full}/releases", params=params
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        items = []
        for release in data:
            published = datetime.strptime(
                release["published_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            if published < datetime.now(timezone.utc) - timedelta(hours=48):
                continue
            items.append(RawItem(
                title=f"{repo_full} - {release['name'] or release['tag_name']}",
                url=release["html_url"],
                source_type=SourceType.GITHUB,
                content=release.get("body", "") or "",
                published_at=published,
                extra={
                    "repo": repo_full,
                    "tag": release["tag_name"],
                    "release_type": "release",
                },
            ))
        return items
