from __future__ import annotations
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import httpx
import xml.etree.ElementTree as ET
from models import RawItem, SourceType
from collectors.base import BaseCollector

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
logger = logging.getLogger(__name__)


class ArXivCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "arxiv"

    async def collect(self) -> list[RawItem]:
        categories = self.config.get("categories", ["cs.DC"])
        max_results = self.config.get("max_results", 20)
        timeout = self.config.get("timeout", 120)

        query = " OR ".join(f"cat:{cat}" for cat in categories[:3])

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        items = []
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(
                        "https://export.arxiv.org/api/query",
                        params=params
                    )
                    if resp.status_code == 429:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"arxiv: rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                    resp.raise_for_status()
                    items = self._parse_response(resp.text)
                    break
            except httpx.TimeoutException:
                logger.warning(f"arxiv: timeout on attempt {attempt + 1}/3")
                if attempt < 2:
                    await asyncio.sleep(10)
                else:
                    logger.error("arxiv: all retries exhausted")
            except Exception as e:
                logger.error(f"arxiv: failed - {e}")
                break

        return items

    def _parse_response(self, xml_text: str) -> list[RawItem]:
        root = ET.fromstring(xml_text)
        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

        for entry in root.findall("atom:entry", ARXIV_NS):
            published_el = entry.find("atom:published", ARXIV_NS)
            if published_el is None:
                continue
            published_str = published_el.text
            published = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            if published < cutoff:
                continue

            title_el = entry.find("atom:title", ARXIV_NS)
            title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
            id_el = entry.find("atom:id", ARXIV_NS)
            link = id_el.text if id_el is not None else ""
            summary_el = entry.find("atom:summary", ARXIV_NS)
            summary = summary_el.text.strip().replace("\n", " ") if summary_el is not None else ""
            authors = [
                a.find("atom:name", ARXIV_NS).text
                for a in entry.findall("atom:author", ARXIV_NS)
                if a.find("atom:name", ARXIV_NS) is not None
            ]
            categories = [
                c.get("term", "")
                for c in entry.findall("atom:category", ARXIV_NS)
            ]

            items.append(RawItem(
                title=title,
                url=link,
                source_type=SourceType.ARXIV,
                content=summary,
                published_at=published,
                extra={
                    "authors": authors,
                    "categories": categories,
                    "arxiv_id": link.split("/abs/")[-1] if "/abs/" in link else "",
                },
            ))
        return items
