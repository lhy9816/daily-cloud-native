import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from formatter import build_feishu_card
from models import AnalyzedItem, SourceType, Recommendation, CategorySection, Digest
from datetime import datetime, timezone

digest = Digest(
    date="2026-03-28",
    top_line="Test top line",
    sections=[
        CategorySection(
            category="GitHub",
            icon="🐙",
            items=[
                AnalyzedItem(
                    title="Test Repo",
                    url="https://github.com/test/test",
                    source_type=SourceType.GITHUB,
                    published_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
                    analysis="Test analysis content",
                    score=8.0,
                    recommendation=Recommendation.MUST_READ,
                )
            ],
        )
    ],
    must_read=[],
)

card = build_feishu_card(digest)
print(json.dumps(card, indent=2, ensure_ascii=False))
