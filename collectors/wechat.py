from __future__ import annotations
from models import SourceType
from collectors.rss_base import RSSCollector


class WeChatCollector(RSSCollector):
    def __init__(self, config: dict):
        super().__init__(config, SourceType.WECHAT)
        self.rsshub_url = config.get("rsshub_url", "http://localhost:1200")
        self.accounts = config.get("accounts", [])

    @property
    def source_name(self) -> str:
        return "wechat"

    async def collect(self) -> list:
        items = []
        hours = self.config.get("hours", 48)
        for account in self.accounts:
            feed_url = f"{self.rsshub_url}/wechat/mp/article/{account}"
            items.extend(self._parse_feed(feed_url, hours))
        return items
