from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
import httpx
import feedparser
from models import RawItem, SourceType
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class TechMediaCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.rsshub_url = config.get("rsshub_url", "http://localhost:1200")
        self.feeds = config.get("feeds", [])

    @property
    def source_name(self) -> str:
        return "tech_media"

    async def collect(self) -> list[RawItem]:
        items = []
        hours = self.config.get("hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        async with httpx.AsyncClient(timeout=30) as client:
            for feed in self.feeds:
                feed_name = feed.get("name", feed.get("path", "unknown"))
                feed_path = feed.get("path", "")
                if not feed_path:
                    continue
                feed_url = f"{self.rsshub_url}/{feed_path}"
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        logger.warning(f"tech_media: {feed_name} returned {resp.status_code}")
                        continue

                    feed_data = feedparser.parse(resp.text)
                    feed_items = 0
                    for entry in feed_data.entries:
                        published = self._parse_time(entry)
                        if published and published < cutoff:
                            continue
                        if not published:
                            published = datetime.now(timezone.utc)
                        items.append(RawItem(
                            title=entry.get("title", ""),
                            url=entry.get("link", ""),
                            source_type=SourceType.TECH_MEDIA,
                            content=entry.get("summary", "") or entry.get("description", ""),
                            published_at=published,
                            extra={
                                "feed": feed_name,
                                "author": entry.get("author", ""),
                            },
                        ))
                        feed_items += 1
                    logger.info(f"tech_media: {feed_name} collected {feed_items} items")
                except Exception as e:
                    logger.error(f"tech_media: {feed_name} failed - {e}")

        return items

    def _parse_time(self, entry: dict) -> datetime | None:
        import time
        for key in ("published_parsed", "updated_parsed"):
            parsed = entry.get(key)
            if parsed:
                ts = time.mktime(parsed)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None
