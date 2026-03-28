from datetime import datetime, timezone
from models import RawItem, AnalyzedItem, SourceType, Recommendation, CategorySection, Digest


def test_raw_item_creation():
    item = RawItem(
        title="Test Paper",
        url="https://example.com/paper",
        source_type=SourceType.ARXIV,
        content="This is an abstract about cloud native scheduling.",
        published_at=datetime(2026, 3, 27, 10, 0, 0),
        extra={"authors": ["Alice", "Bob"]},
    )
    assert item.title == "Test Paper"
    assert item.source_type == SourceType.ARXIV
    assert len(item.extra["authors"]) == 2


def test_analyzed_item_score_bounds():
    item = AnalyzedItem(
        title="Test",
        url="https://example.com",
        source_type=SourceType.GITHUB,
        published_at=datetime(2026, 3, 27),
        score=8.5,
        recommendation=Recommendation.MUST_READ,
    )
    assert 0 <= item.score <= 10
    assert item.recommendation == Recommendation.MUST_READ


def test_digest_structure():
    digest = Digest(date="2026-03-27", top_line="Important update today")
    section = CategorySection(category="GitHub", icon="🐙", items=[])
    digest.sections.append(section)
    assert len(digest.sections) == 1
    assert digest.date == "2026-03-27"


def test_raw_item_defaults():
    item = RawItem(title="T", url="https://x.com", source_type=SourceType.BLOG)
    assert item.content == ""
    assert isinstance(item.extra, dict)
    assert isinstance(item.published_at, datetime)
