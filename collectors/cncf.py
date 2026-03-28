from __future__ import annotations
from models import SourceType
from collectors.rss_base import RSSCollector


class CNCFCollector(RSSCollector):
    def __init__(self, config: dict):
        super().__init__(config, SourceType.CNCF)

    @property
    def source_name(self) -> str:
        return "cncf"

    async def collect(self) -> list:
        feeds = self.config.get("feeds", [])
        hours = self.config.get("hours", 48)
        items = []
        for feed_url in feeds:
            items.extend(self._parse_feed(feed_url, hours))
        return items
