from __future__ import annotations
import asyncio
import logging
import httpx
from models import Digest
from formatter import build_feishu_card

logger = logging.getLogger(__name__)


async def send_to_feishu(digest: Digest, webhook_url: str) -> bool:
    payload = build_feishu_card(digest)
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code", -1) == 0:
                    logger.info("Feishu push succeeded")
                    return True
                logger.warning(f"Feishu API error: {data}")
        except Exception as e:
            logger.warning(f"Feishu push attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                await asyncio.sleep(10)
    logger.error("Feishu push failed after 3 attempts")
    return False
