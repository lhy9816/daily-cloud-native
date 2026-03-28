import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx
from formatter import build_feishu_card
from models import AnalyzedItem, SourceType, Recommendation, CategorySection, Digest
from datetime import datetime, timezone

digest = Digest(
    date="2026-03-28",
    top_line="Test: Harbor and K8s updates are highlights today.",
    sections=[
        CategorySection(
            category="GitHub",
            icon="🐙",
            items=[
                AnalyzedItem(
                    title="goharbor/harbor",
                    url="https://github.com/goharbor/harbor",
                    source_type=SourceType.GITHUB,
                    published_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
                    analysis="Harbor is an open source container image registry with enterprise security features.",
                    score=9.0,
                    recommendation=Recommendation.MUST_READ,
                )
            ],
        )
    ],
    must_read=[],
)

card = build_feishu_card(digest)
r = httpx.post(
    "https://open.feishu.cn/open-apis/bot/v2/hook/0237ebbf-22e1-4534-a250-60936b7beb7c",
    json=card,
    timeout=10,
)
print("Status:", r.status_code)
print("Response:", r.json())
