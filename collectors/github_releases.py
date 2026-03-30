from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
import httpx
import xml.etree.ElementTree as ET
from models import RawItem, SourceType
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class GitHubReleasesCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "github_releases"

    async def collect(self) -> list[RawItem]:
        repos = self.config.get("repos", [])
        hours = self.config.get("hours", 72)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        items = []

        async with httpx.AsyncClient(timeout=30) as client:
            for repo in repos:
                url = f"https://github.com/{repo}/releases.atom"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(f"github_releases: {repo} returned {resp.status_code}")
                        continue
                    repo_items = self._parse_atom(resp.text, repo, cutoff)
                    items.extend(repo_items)
                    if repo_items:
                        logger.info(f"github_releases: {repo} collected {len(repo_items)} items")
                except Exception as e:
                    logger.error(f"github_releases: {repo} failed - {e}")

        return items

    def _parse_atom(self, xml_text: str, repo: str, cutoff: datetime) -> list[RawItem]:
        items = []
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ATOM_NS):
            updated_el = entry.find("atom:updated", ATOM_NS)
            if updated_el is None:
                continue
            try:
                published = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if published < cutoff:
                continue

            title_el = entry.find("atom:title", ATOM_NS)
            title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
            link_el = entry.find("atom:link", ATOM_NS)
            link = link_el.get("href", "") if link_el is not None else ""
            if not link:
                for l in entry.findall("atom:link", ATOM_NS):
                    if l.get("rel") == "alternate":
                        link = l.get("href", "")
                        break
            content_el = entry.find("atom:content", ATOM_NS)
            content = content_el.text if content_el is not None else ""

            items.append(RawItem(
                title=f"[{repo.split('/')[-1]}] {title}",
                url=link,
                source_type=SourceType.GITHUB,
                content=content[:1000] if content else "",
                published_at=published,
                extra={"repo": repo, "type": "release"},
            ))
        return items
