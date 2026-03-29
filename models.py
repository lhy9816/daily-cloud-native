from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    GITHUB = "github"
    CNCF = "cncf"
    ARXIV = "arxiv"
    BLOG = "blog"
    TECH_MEDIA = "tech_media"


class Recommendation(str, Enum):
    MUST_READ = "must-read"
    RECOMMENDED = "recommended"
    MONITOR = "monitor"
    OPTIONAL = "optional"


class RawItem(BaseModel):
    title: str
    url: str
    source_type: SourceType
    content: str = ""
    published_at: datetime = Field(default_factory=datetime.utcnow)
    extra: dict = Field(default_factory=dict)


class AnalyzedItem(BaseModel):
    title: str
    url: str
    source_type: SourceType
    published_at: datetime
    extra: dict = Field(default_factory=dict)
    analysis: str = ""
    score: float = Field(ge=0, le=10, default=5.0)
    recommendation: Recommendation = Recommendation.OPTIONAL


class CategorySection(BaseModel):
    category: str
    icon: str
    items: list[AnalyzedItem] = Field(default_factory=list)


class Digest(BaseModel):
    date: str
    top_line: str = ""
    sections: list[CategorySection] = Field(default_factory=list)
    must_read: list[AnalyzedItem] = Field(default_factory=list)
    monitor: list[AnalyzedItem] = Field(default_factory=list)
    optional: list[AnalyzedItem] = Field(default_factory=list)
