from datetime import datetime, timezone
from models import RawItem, AnalyzedItem, SourceType, Recommendation
from processor import dedup_items, rank_items, group_by_category


def test_dedup_removes_duplicate_urls():
    items = [
        RawItem(title="A", url="https://x.com/1", source_type=SourceType.BLOG),
        RawItem(title="B", url="https://x.com/1", source_type=SourceType.BLOG),
        RawItem(title="C", url="https://x.com/2", source_type=SourceType.BLOG),
    ]
    result = dedup_items(items)
    assert len(result) == 2


def test_dedup_removes_previous_day_urls():
    items = [
        RawItem(title="A", url="https://x.com/1", source_type=SourceType.BLOG),
        RawItem(title="B", url="https://x.com/2", source_type=SourceType.BLOG),
    ]
    prev_urls = {"https://x.com/1"}
    result = dedup_items(items, prev_urls)
    assert len(result) == 1
    assert result[0].url == "https://x.com/2"


def test_rank_items_sorts_by_score():
    items = [
        AnalyzedItem(
            title="Low", url="https://x.com/1",
            source_type=SourceType.BLOG,
            published_at=datetime.now(timezone.utc),
            score=3.0,
        ),
        AnalyzedItem(
            title="High", url="https://x.com/2",
            source_type=SourceType.BLOG,
            published_at=datetime.now(timezone.utc),
            score=9.0,
        ),
        AnalyzedItem(
            title="Mid", url="https://x.com/3",
            source_type=SourceType.BLOG,
            published_at=datetime.now(timezone.utc),
            score=6.0,
        ),
    ]
    result = rank_items(items)
    assert result[0].title == "High"
    assert result[1].title == "Mid"
    assert result[2].title == "Low"


def test_group_by_category():
    items = [
        AnalyzedItem(
            title="Paper 1", url="https://x.com/1",
            source_type=SourceType.ARXIV,
            published_at=datetime.now(timezone.utc),
            score=8.0,
            recommendation=Recommendation.MUST_READ,
        ),
        AnalyzedItem(
            title="Repo 1", url="https://x.com/2",
            source_type=SourceType.GITHUB,
            published_at=datetime.now(timezone.utc),
            score=7.0,
            recommendation=Recommendation.RECOMMENDED,
        ),
        AnalyzedItem(
            title="Paper 2", url="https://x.com/3",
            source_type=SourceType.ARXIV,
            published_at=datetime.now(timezone.utc),
            score=5.0,
            recommendation=Recommendation.OPTIONAL,
        ),
    ]
    sections = group_by_category(items, top_n=3)
    assert len(sections) == 2
    arxiv_section = next(s for s in sections if s.category == "论文")
    assert len(arxiv_section.items) == 2
    assert arxiv_section.items[0].score >= arxiv_section.items[1].score
