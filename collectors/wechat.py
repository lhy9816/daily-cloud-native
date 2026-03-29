from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
import httpx
import feedparser
from models import RawItem, SourceType
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class WeChatCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self.rsshub_url = config.get("rsshub_url", "http://localhost:1200")
        self.accounts = config.get("accounts", [])

    @property
    def source_name(self) -> str:
        return "wechat"

    async def collect(self) -> list[RawItem]:
        items = []
        hours = self.config.get("hours", 168)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        async with httpx.AsyncClient(timeout=30) as client:
            for account in self.accounts:
                feed_url = f"{self.rsshub_url}/wechat/sogou/{account}"
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        logger.warning(f"wechat: {account} returned {resp.status_code}")
                        continue

                    feed = feedparser.parse(resp.text)
                    account_items = 0
                    for entry in feed.entries:
                        published = self._parse_time(entry)
                        if published and published < cutoff:
                            continue
                        if not published:
                            published = datetime.now(timezone.utc)
                        items.append(RawItem(
                            title=entry.get("title", ""),
                            url=entry.get("link", ""),
                            source_type=SourceType.WECHAT,
                            content=entry.get("summary", "") or entry.get("description", ""),
                            published_at=published,
                            extra={
                                "account": account,
                                "author": entry.get("author", ""),
                            },
                        ))
                        account_items += 1
                    logger.info(f"wechat: {account} collected {account_items} items")
                except Exception as e:
                    logger.error(f"wechat: {account} failed - {e}")

        return items

    def _parse_time(self, entry: dict) -> datetime | None:
        import time
        for key in ("published_parsed", "updated_parsed"):
            parsed = entry.get(key)
            if parsed:
                ts = time.mktime(parsed)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None
