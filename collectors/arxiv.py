from __future__ import annotations
from datetime import datetime, timedelta, timezone
import httpx
import xml.etree.ElementTree as ET
from models import RawItem, SourceType
from collectors.base import BaseCollector

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArXivCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "arxiv"

    async def collect(self) -> list[RawItem]:
        categories = self.config.get("categories", ["cs.DC"])
        keywords = self.config.get("keywords", [])
        max_results = self.config.get("max_results", 30)

        query_parts = []
        for cat in categories:
            query_parts.append(f"cat:{cat}")
        for kw in keywords[:5]:
            query_parts.append(f"all:{kw}")
        query = " OR ".join(query_parts)

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://export.arxiv.org/api/query", params=params
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
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
