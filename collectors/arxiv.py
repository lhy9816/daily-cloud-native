from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
import httpx
import xml.etree.ElementTree as ET
from models import RawItem, SourceType
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

RSS_NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "dc": "http://purl.org/dc/elements/1.1/", "atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/"}


class ArXivCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "arxiv"

    async def collect(self) -> list[RawItem]:
        rss_url = self.config.get("rss_url", "https://rss.arxiv.org/rss/cs.DC+cs.SE+cs.LG")
        hours = self.config.get("hours", 72)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(rss_url)
                resp.raise_for_status()
            items = self._parse_rss(resp.text, cutoff)
            logger.info(f"arxiv: collected {len(items)} items from {rss_url}")
            return items
        except httpx.TimeoutException:
            logger.warning("arxiv: request timed out")
            return []
        except Exception as e:
            logger.error(f"arxiv: failed - {e}")
            return []

    def _parse_rss(self, rss_text: str, cutoff: datetime) -> list[RawItem]:
        items = []
        root = ET.fromstring(rss_text)
        for item in root.findall(".//item"):
            title_el = item.find("title")
            title = title_el.text.strip() if title_el is not None else ""
            link_el = item.find("link")
            link = link_el.text if link_el is not None else ""
            desc_el = item.find("description")
            content = desc_el.text if desc_el is not None else ""

            pub_date_el = item.find("dc:date")
            published = None
            if pub_date_el is not None and pub_date_el.text:
                try:
                    published = datetime.fromisoformat(pub_date_el.text.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            if published and published < cutoff:
                continue
            if not published:
                published = datetime.now(timezone.utc)

            items.append(RawItem(
                title=title,
                url=link,
                source_type=SourceType.ARXIV,
                content=content[:800] if content else "",
                published_at=published,
                extra={
                    "arxiv_id": link.split("/abs/")[-1] if "/abs/" in link else "",
                },
            ))
        return items
