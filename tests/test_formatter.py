from datetime import datetime, timezone
from models import AnalyzedItem, SourceType, Recommendation, CategorySection, Digest
from formatter import build_feishu_card, build_markdown


def _make_item(title: str, score: float, rec: Recommendation, source: SourceType) -> AnalyzedItem:
    return AnalyzedItem(
        title=title,
        url=f"https://example.com/{title}",
        source_type=source,
        published_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
        analysis="This is a test analysis with technical details.",
        score=score,
        recommendation=rec,
        extra={"stars": 1000},
    )


def test_build_feishu_card_structure():
    digest = Digest(
        date="2026-03-27",
        top_line="Today's top news.",
        sections=[
            CategorySection(
                category="GitHub",
                icon="🐙",
                items=[_make_item("Repo1", 8.0, Recommendation.MUST_READ, SourceType.GITHUB)],
            ),
        ],
        must_read=[_make_item("Must1", 9.0, Recommendation.MUST_READ, SourceType.ARXIV)],
    )
    card = build_feishu_card(digest)
    assert card["msg_type"] == "interactive"
    assert "header" in card["card"]
    elements = card["card"]["elements"]
    assert any("GitHub" in str(e) for e in elements)


def test_build_markdown_structure():
    digest = Digest(
        date="2026-03-27",
        top_line="Important update.",
        sections=[
            CategorySection(
                category="论文",
                icon="🔬",
                items=[_make_item("Paper1", 8.5, Recommendation.MUST_READ, SourceType.ARXIV)],
            ),
        ],
        must_read=[],
        monitor=[],
    )
    md = build_markdown(digest)
    assert "# 每日云原生速递" in md
    assert "2026-03-27" in md
    assert "## 🔬 论文" in md
    assert "Paper1" in md
