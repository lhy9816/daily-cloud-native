from __future__ import annotations
import time
import feedparser
from datetime import datetime, timedelta, timezone
from models import RawItem, SourceType
from collectors.base import BaseCollector


class RSSCollector(BaseCollector):
    def __init__(self, config: dict, source_type: SourceType):
        super().__init__(config)
        self.source_type = source_type

    def _parse_feed(self, feed_url: str, hours: int = 48) -> list[RawItem]:
        feed = feedparser.parse(feed_url)
        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        for entry in feed.entries:
            published = self._parse_time(entry)
            if published and published < cutoff:
                continue
            items.append(RawItem(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source_type=self.source_type,
                content=entry.get("summary", "") or "",
                published_at=published or datetime.now(timezone.utc),
                extra={
                    "feed_url": feed_url,
                    "authors": [a.get("name", "") for a in entry.get("authors", [])],
                },
            ))
        return items

    def _parse_time(self, entry: dict) -> datetime | None:
        for key in ("published_parsed", "updated_parsed"):
            parsed = entry.get(key)
            if parsed:
                try:
                    ts = time.mktime(parsed)
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                except (OverflowError, OSError, ValueError):
                    continue
        return None
