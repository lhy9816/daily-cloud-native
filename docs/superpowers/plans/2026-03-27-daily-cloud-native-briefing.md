# Daily Cloud Native Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily automated tool that collects cloud native updates from 5 source types, performs AI deep analysis, pushes a rich digest to Feishu group chat, and archives as Markdown to GitHub.

**Architecture:** Modular Python scripts with asyncio-concurrent Collectors, a centralized LLM processing pipeline with source-type-specific prompts, Feishu Interactive Card formatting, and a GitHub archiver. Runs daily at 08:00 CST via Windows Task Scheduler.

**Tech Stack:** Python 3.10+, httpx (async HTTP), feedparser (RSS), openai (LLM), pydantic (models), pyyaml (config), python-dotenv (env)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `models.py` | Pydantic data models: RawItem, AnalyzedItem, Digest |
| `config.yaml` | All configuration (sources, LLM, Feishu, GitHub archive) |
| `.env.example` | Template for environment variables |
| `.gitignore` | Git ignore rules |
| `requirements.txt` | Python dependencies |
| `collectors/base.py` | BaseCollector abstract class with async interface |
| `collectors/github.py` | GitHub REST API collector |
| `collectors/cncf.py` | CNCF/K8s RSS collector |
| `collectors/arxiv.py` | ArXiv API collector |
| `collectors/blogs.py` | Tech blog RSS collector |
| `collectors/wechat.py` | WeChat RSSHub collector |
| `prompts/paper_prompt.md` | LLM system prompt for papers |
| `prompts/github_prompt.md` | LLM system prompt for GitHub projects |
| `prompts/blog_prompt.md` | LLM system prompt for blog articles |
| `prompts/wechat_prompt.md` | LLM system prompt for WeChat articles |
| `prompts/summary_prompt.md` | LLM system prompt for top line summary |
| `processor.py` | Dedup, LLM batch analysis, scoring, ranking |
| `formatter.py` | Feishu Interactive Card JSON builder + Markdown renderer |
| `notifier.py` | Feishu Webhook POST with retry |
| `archiver.py` | Markdown file write + git commit + push |
| `main.py` | Entry point, orchestrates full pipeline |
| `tests/test_models.py` | Tests for data models |
| `tests/test_processor.py` | Tests for dedup and scoring logic |
| `tests/test_formatter.py` | Tests for Feishu card and Markdown output |

---

### Task 1: Project Scaffolding and Data Models

**Files:**
- Create: `models.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `content/.gitkeep`
- Create: `data/.gitkeep`
- Create: `logs/.gitkeep`
- Create: `tests/__init__.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.env
data/
logs/
*.egg-info/
dist/
build/
.venv/
venv/
```

- [ ] **Step 2: Create `requirements.txt`**

```
httpx>=0.27.0
feedparser>=6.0.0
openai>=1.0.0
pydantic>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
lxml>=5.0.0
```

- [ ] **Step 3: Create `.env.example`**

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_BASE_URL=
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxx
```

- [ ] **Step 4: Create directory placeholder files**

Create empty files: `content/.gitkeep`, `data/.gitkeep`, `logs/.gitkeep`, `tests/__init__.py`, `collectors/__init__.py`

- [ ] **Step 5: Create `models.py` with all data models**

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    GITHUB = "github"
    CNCF = "cncf"
    ARXIV = "arxiv"
    BLOG = "blog"
    WECHAT = "wechat"


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
```

- [ ] **Step 6: Create `tests/test_models.py`**

```python
from datetime import datetime
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
    section = CategorySection(
        category="GitHub",
        icon="🐙",
        items=[],
    )
    digest.sections.append(section)
    assert len(digest.sections) == 1
    assert digest.date == "2026-03-27"


def test_raw_item_defaults():
    item = RawItem(title="T", url="https://x.com", source_type=SourceType.BLOG)
    assert item.content == ""
    assert isinstance(item.extra, dict)
    assert isinstance(item.published_at, datetime)
```

- [ ] **Step 7: Run tests to verify**

Run: `python -m pytest tests/test_models.py -v`
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git init
git add models.py requirements.txt .env.example .gitignore content/.gitkeep data/.gitkeep logs/.gitkeep tests/__init__.py tests/test_models.py collectors/__init__.py
git commit -m "chore: project scaffolding and data models"
```

---

### Task 2: Configuration System

**Files:**
- Create: `config.yaml`
- Create: `config_loader.py`

- [ ] **Step 1: Create `config.yaml` with all settings**

```yaml
sources:
  github:
    token: "${GITHUB_TOKEN}"
    keywords:
      - kubernetes
      - cloud-native
      - llm-inference
      - ai-agent
      - gpu-scheduling
      - volcano
      - kserve
      - triton
      - vllm
      - karpenter
      - cluster-api
      - kube-bench
      - rancher
      - k3s
      - crossplane
      - argo
      - backstage
      - kyverno
      - open-telemetry
      - cilium
      - istio
      - envoy
    watch_repos:
      - "kubernetes/kubernetes"
      - "cilium/cilium"
      - "istio/istio"
      - "envoyproxy/envoy"
      - "prometheus/prometheus"
      - "argoproj/argo-cd"
      - "volcano-sh/volcano"
      - "kserve/kserve"
      - "vllm-project/vllm"
      - "triton-inference-server/triton"
      - "langchain-ai/langchain"
      - "crewAIInc/crewAI"
      - "open-telemetry/opentelemetry"
      - "kyverno/kyverno"
      - "crossplane/crossplane"
      - "kubeflow/kubeflow"
      - "dapr/dapr"
      - "knative/serving"
  arxiv:
    categories:
      - "cs.DC"
      - "cs.SE"
      - "cs.LG"
    keywords:
      - kubernetes
      - container
      - cloud-native
      - scheduling
      - inference
      - LLM serving
      - GPU
      - cluster
      - MLOps
      - AI agent
      - operator
      - service mesh
      - observability
      - ebpf
      - serverless
    max_results: 30
  cncf:
    feeds:
      - "https://www.cncf.io/feed/"
      - "https://kubernetes.io/blog/feed.xml"
  blogs:
    feeds:
      - "https://www.infoq.com/feed/"
      - "https://thenewstack.io/feed/"
      - "https://aws.amazon.com/blogs/containers/feed/"
      - "https://cloud.google.com/blog/feed"
  wechat:
    rsshub_url: "http://localhost:1200"
    accounts:
      - "cloud-native-lab"
      - "KubeSphere"
      - "DaoCloud"
      - "aliyun-cloudnative"

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "${LLM_API_KEY}"
  base_url: ""
  batch_size: 6
  max_output_tokens: 500

feishu:
  webhook_url: "${FEISHU_WEBHOOK_URL}"

github_archive:
  repo_path: "."
  content_dir: "content"
  remote: "origin"
  branch: "main"

schedule:
  timezone: "Asia/Shanghai"
  time: "08:00"
  timeout_minutes: 10
```

- [ ] **Step 2: Create `config_loader.py`**

```python
from __future__ import annotations
import os
import re
from pathlib import Path
import yaml
from dotenv import load_dotenv


def _resolve_env_vars(value: str) -> str:
    pattern = re.compile(r"\$\{(\w+)\}")
    def _replace(match: re.Match) -> str:
        return os.environ.get(match.group(1), match.group(0))
    return pattern.sub(_replace, value)


def _resolve_dict(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _resolve_dict(v)
        elif isinstance(v, list):
            result[k] = [
                _resolve_env_vars(i) if isinstance(i, str) else i
                for i in v
            ]
        else:
            result[k] = v
    return result


def load_config(config_path: str = "config.yaml") -> dict:
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return _resolve_dict(cfg)
```

- [ ] **Step 3: Commit**

```bash
git add config.yaml config_loader.py
git commit -m "chore: add configuration system with env var resolution"
```

---

### Task 3: Base Collector and GitHub Collector

**Files:**
- Create: `collectors/base.py`
- Create: `collectors/github.py`
- Test: `tests/test_collectors.py`

- [ ] **Step 1: Create `collectors/base.py`**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from models import RawItem


class BaseCollector(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def collect(self) -> list[RawItem]:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...
```

- [ ] **Step 2: Create `collectors/github.py`**

```python
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import httpx
from models import RawItem, SourceType
from collectors.base import BaseCollector


class GitHubCollector(BaseCollector):
    BASE_URL = "https://api.github.com"

    def __init__(self, config: dict):
        super().__init__(config)
        self.headers = {
            "Accept": "application/vnd.github+3+json",
            "Authorization": f"Bearer {self.config['token']}",
        }

    @property
    def source_name(self) -> str:
        return "github"

    async def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        tasks = []
        keywords = self.config.get("keywords", [])
        for kw in keywords:
            tasks.append(self._search_repos(kw))
        for repo in self.config.get("watch_repos", []):
            tasks.append(self._get_repo_releases(repo))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        seen_urls: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                continue
            for item in result:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)
        return items

    async def _search_repos(self, keyword: str) -> list[RawItem]:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d")
        params = {
            "q": f"{keyword} pushed:>{since}",
            "sort": "stars",
            "order": "desc",
            "per_page": 5,
        }
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(f"{self.BASE_URL}/search/repositories", params=params)
            resp.raise_for_status()
            data = resp.json()
        items = []
        for repo in data.get("items", []):
            items.append(RawItem(
                title=repo["full_name"],
                url=repo["html_url"],
                source_type=SourceType.GITHUB,
                content=repo.get("description", "") or "",
                published_at=datetime.strptime(
                    repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc),
                extra={
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "description": repo.get("description", ""),
                },
            ))
        return items

    async def _get_repo_releases(self, repo_full: str) -> list[RawItem]:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        params = {"per_page": 5}
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{repo_full}/releases", params=params
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        items = []
        for release in data:
            published = datetime.strptime(
                release["published_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            if published < datetime.now(timezone.utc) - timedelta(hours=24):
                continue
            items.append(RawItem(
                title=f"{repo_full} - {release['name'] or release['tag_name']}",
                url=release["html_url"],
                source_type=SourceType.GITHUB,
                content=release.get("body", "") or "",
                published_at=published,
                extra={
                    "repo": repo_full,
                    "tag": release["tag_name"],
                    "release_type": "release",
                },
            ))
        return items
```

- [ ] **Step 3: Create `tests/test_collectors.py`**

```python
from collectors.base import BaseCollector
from models import RawItem, SourceType


def test_base_collector_is_abstract():
    try:
        BaseCollector(config={})
        assert False, "Should not be instantiable"
    except TypeError:
        pass


def test_collector_subclass():
    class DummyCollector(BaseCollector):
        @property
        def source_name(self) -> str:
            return "dummy"

        async def collect(self) -> list[RawItem]:
            return [
                RawItem(
                    title="Test",
                    url="https://example.com",
                    source_type=SourceType.BLOG,
                )
            ]

    c = DummyCollector(config={})
    assert c.source_name == "dummy"
    assert isinstance(c.config, dict)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_collectors.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add collectors/base.py collectors/github.py tests/test_collectors.py
git commit -m "feat: add base collector and GitHub collector"
```

---

### Task 4: RSS-Based Collectors (CNCF, Blogs, WeChat)

**Files:**
- Create: `collectors/rss_base.py`
- Create: `collectors/cncf.py`
- Create: `collectors/blogs.py`
- Create: `collectors/wechat.py`

- [ ] **Step 1: Create `collectors/rss_base.py`**

```python
from __future__ import annotations
import feedparser
from datetime import datetime, timedelta, timezone
from models import RawItem, SourceType
from collectors.base import BaseCollector


class RSSCollector(BaseCollector):
    def __init__(self, config: dict, source_type: SourceType):
        super().__init__(config)
        self.source_type = source_type

    def _parse_feed(self, feed_url: str, hours: int = 24) -> list[RawItem]:
        feed = feedparser.parse(feed_url)
        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        for entry in feed.entries:
            published = self._parse_time(entry)
            if published and published < cutoff:
                continue
            items.append(RawItem(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source_type=self.source_type,
                content=entry.get("summary", "") or "",
                published_at=published or datetime.now(timezone.utc),
                extra={
                    "feed_url": feed_url,
                    "authors": [a.get("name", "") for a in entry.get("authors", [])],
                },
            ))
        return items

    def _parse_time(self, entry: dict) -> datetime | None:
        if "published_parsed" in entry and entry["published_parsed"]:
            import time
            ts = time.mktime(entry["published_parsed"])
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if "updated_parsed" in entry and entry["updated_parsed"]:
            import time
            ts = time.mktime(entry["updated_parsed"])
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None
```

- [ ] **Step 2: Create `collectors/cncf.py`**

```python
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
        items = []
        for feed_url in feeds:
            items.extend(self._parse_feed(feed_url))
        return items
```

- [ ] **Step 3: Create `collectors/blogs.py`**

```python
from __future__ import annotations
from models import SourceType
from collectors.rss_base import RSSCollector


class BlogsCollector(RSSCollector):
    def __init__(self, config: dict):
        super().__init__(config, SourceType.BLOG)

    @property
    def source_name(self) -> str:
        return "blogs"

    async def collect(self) -> list:
        feeds = self.config.get("feeds", [])
        items = []
        for feed_url in feeds:
            items.extend(self._parse_feed(feed_url))
        return items
```

- [ ] **Step 4: Create `collectors/wechat.py`**

```python
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
        for account in self.accounts:
            feed_url = f"{self.rsshub_url}/wechat/mp/article/{account}"
            items.extend(self._parse_feed(feed_url))
        return items
```

- [ ] **Step 5: Commit**

```bash
git add collectors/rss_base.py collectors/cncf.py collectors/blogs.py collectors/wechat.py
git commit -m "feat: add RSS-based collectors for CNCF, blogs, and WeChat"
```

---

### Task 5: ArXiv Collector

**Files:**
- Create: `collectors/arxiv.py`

- [ ] **Step 1: Create `collectors/arxiv.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import httpx
import xml.etree.ElementTree as ET
from models import RawItem, SourceType
from collectors.base import BaseCollector

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArXivCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "arxiv"

    async def collect(self) -> list[RawItem]:
        categories = self.config.get("categories", ["cs.DC"])
        keywords = self.config.get("keywords", [])
        max_results = self.config.get("max_results", 30)

        query_parts = []
        for cat in categories:
            query_parts.append(f"cat:{cat}")
        for kw in keywords:
            query_parts.append(f"all:{kw}")
        query = " OR ".join(query_parts)

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "http://export.arxiv.org/api/query", params=params
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        for entry in root.findall("atom:entry", ARXIV_NS):
            published_str = entry.find("atom:published", ARXIV_NS).text
            published = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            if published < cutoff:
                continue

            title = entry.find("atom:title", ARXIV_NS).text.strip().replace("\n", " ")
            link = entry.find("atom:id", ARXIV_NS).text
            summary = (
                entry.find("atom:summary", ARXIV_NS).text.strip().replace("\n", " ")
            )
            authors = [
                a.find("atom:name", ARXIV_NS).text
                for a in entry.findall("atom:author", ARXIV_NS)
            ]
            categories = [
                c.get("term", "")
                for c in entry.findall("atom:category", ARXIV_NS)
            ]

            items.append(RawItem(
                title=title,
                url=link,
                source_type=SourceType.ARXIV,
                content=summary,
                published_at=published,
                extra={
                    "authors": authors,
                    "categories": categories,
                    "arxiv_id": link.split("/abs/")[-1] if "/abs/" in link else "",
                },
            ))
        return items
```

- [ ] **Step 2: Commit**

```bash
git add collectors/arxiv.py
git commit -m "feat: add ArXiv collector"
```

---

### Task 6: LLM Prompt Templates

**Files:**
- Create: `prompts/paper_prompt.md`
- Create: `prompts/github_prompt.md`
- Create: `prompts/blog_prompt.md`
- Create: `prompts/wechat_prompt.md`
- Create: `prompts/summary_prompt.md`

- [ ] **Step 1: Create `prompts/paper_prompt.md`**

```markdown
你是一位云原生和分布式系统领域的资深技术专家。请对以下论文进行深度技术分析。

要求：
1. 用中文回答，每条分析 150-250 字
2. 必须覆盖以下维度：
   - 核心问题：这篇论文解决了什么问题
   - 关键架构：系统或方法的整体架构设计思路
   - 重要技巧：核心技术创新点、trick、关键设计选择
   - 实验收益：关键数据、benchmark 对比结果、提升幅度
   - 贡献总结：一句话概括核心贡献
3. 给出推荐等级：must-read / recommended / optional
4. 给出 1-10 的评分

输出格式（严格 JSON）：
{
  "analysis": "...",
  "score": 8,
  "recommendation": "must-read"
}
```

- [ ] **Step 2: Create `prompts/github_prompt.md`**

```markdown
你是一位云原生领域的资深工程师。请对以下 GitHub 项目进行技术分析。

要求：
1. 用中文回答，每条分析 100-200 字
2. 必须覆盖以下维度：
   - 项目定位：这个项目是做什么的
   - 技术亮点：为什么值得关注，有什么独特的技术特色
   - 社区热度：star 数和近期活跃度
   - 实用性：能不能直接使用，适用什么场景
3. 给出推荐等级：must-read / recommended / optional
4. 给出 1-10 的评分

输出格式（严格 JSON）：
{
  "analysis": "...",
  "score": 7,
  "recommendation": "recommended"
}
```

- [ ] **Step 3: Create `prompts/blog_prompt.md`**

```markdown
你是一位云原生领域的技术传播者。请对以下技术博客/工程文章进行深度分析。

要求：
1. 用中文回答，每条分析 100-200 字
2. 必须覆盖以下维度：
   - 核心话题：这篇文章讲什么技术
   - 技术要点：关键概念、原理、设计思路（用通俗易懂的语言）
   - 实践价值：能学到什么、怎么应用到实际工作中
   - 影响分析：对行业或技术方向的影响
3. 给出推荐等级：must-read / recommended / optional
4. 给出 1-10 的评分

输出格式（严格 JSON）：
{
  "analysis": "...",
  "score": 7,
  "recommendation": "recommended"
}
```

- [ ] **Step 4: Create `prompts/wechat_prompt.md`**

Content is identical to `prompts/blog_prompt.md` (WeChat articles use the same analysis format as blog articles).

```markdown
你是一位云原生领域的技术传播者。请对以下微信公众号文章进行深度分析。

要求：
1. 用中文回答，每条分析 100-200 字
2. 必须覆盖以下维度：
   - 核心话题：这篇文章讲什么技术
   - 技术要点：关键概念、原理、设计思路（用通俗易懂的语言）
   - 实践价值：能学到什么、怎么应用到实际工作中
   - 影响分析：对行业或技术方向的影响
3. 给出推荐等级：must-read / recommended / optional
4. 给出 1-10 的评分

输出格式（严格 JSON）：
{
  "analysis": "...",
  "score": 7,
  "recommendation": "recommended"
}
```

- [ ] **Step 5: Create `prompts/summary_prompt.md`**

```markdown
你是一位资深云原生技术编辑。基于以下今日云原生速递的所有条目，生成一段 Top Line 摘要。

要求：
1. 用中文，50-100 字
2. 概括今天最重要的 2-4 条动态
3. 语气简洁、客观、有信息量
4. 不要列举所有条目，只提炼最关键的

直接输出摘要文本，不需要 JSON 格式。
```

- [ ] **Step 6: Commit**

```bash
git add prompts/
git commit -m "feat: add LLM prompt templates for all source types"
```

---

### Task 7: Processor (Dedup + LLM Analysis + Scoring)

**Files:**
- Create: `processor.py`
- Test: `tests/test_processor.py`

- [ ] **Step 1: Create `tests/test_processor.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_processor.py -v`
Expected: FAIL (ImportError: No module named 'processor')

- [ ] **Step 3: Create `processor.py`**

```python
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from models import (
    RawItem, AnalyzedItem, SourceType, Recommendation,
    CategorySection, Digest,
)

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    SourceType.ARXIV: ("论文", "🔬"),
    SourceType.GITHUB: ("GitHub", "🐙"),
    SourceType.CNCF: ("CNCF / K8s", "☁️"),
    SourceType.BLOG: ("技术博客", "📝"),
    SourceType.WECHAT: ("公众号", "💬"),
}

PROMPT_MAP = {
    SourceType.ARXIV: "prompts/paper_prompt.md",
    SourceType.GITHUB: "prompts/github_prompt.md",
    SourceType.BLOG: "prompts/blog_prompt.md",
    SourceType.WECHAT: "prompts/wechat_prompt.md",
}


def dedup_items(
    items: list[RawItem],
    prev_urls: set[str] | None = None,
) -> list[RawItem]:
    seen: set[str] = set()
    result: list[RawItem] = []
    prev = prev_urls or set()
    for item in items:
        if item.url in seen or item.url in prev:
            continue
        seen.add(item.url)
        result.append(item)
    return result


def rank_items(items: list[AnalyzedItem]) -> list[AnalyzedItem]:
    return sorted(items, key=lambda x: x.score, reverse=True)


def group_by_category(
    items: list[AnalyzedItem],
    top_n: int = 3,
) -> list[CategorySection]:
    groups: dict[SourceType, list[AnalyzedItem]] = {}
    for item in items:
        groups.setdefault(item.source_type, []).append(item)
    sections = []
    for source_type, group_items in groups.items():
        sorted_items = sorted(group_items, key=lambda x: x.score, reverse=True)
        cat_name, icon = CATEGORY_MAP.get(source_type, (source_type.value, "📌"))
        sections.append(CategorySection(
            category=cat_name,
            icon=icon,
            items=sorted_items[:top_n],
        ))
    sections.sort(key=lambda s: max((i.score for i in s.items), default=0), reverse=True)
    return sections


def load_prev_urls(data_dir: str = "data") -> set[str]:
    data_path = Path(data_dir)
    if not data_path.exists():
        return set()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_file = data_path / f"{yesterday}.json"
    if not prev_file.exists():
        return set()
    try:
        data = json.loads(prev_file.read_text(encoding="utf-8"))
        return {item["url"] for item in data.get("raw_items", [])}
    except (json.JSONDecodeError, KeyError):
        return set()


def _load_prompt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _build_user_message(item: RawItem) -> str:
    parts = [f"标题: {item.title}", f"链接: {item.url}"]
    if item.content:
        parts.append(f"内容: {item.content}")
    if item.extra:
        for k, v in item.extra.items():
            if isinstance(v, list):
                v = ", ".join(str(i) for i in v)
            parts.append(f"{k}: {v}")
    return "\n".join(parts)


def _parse_llm_response(text: str) -> dict:
    text = text.strip()
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"analysis": text, "score": 5.0, "recommendation": "optional"}


def analyze_items(
    items: list[RawItem],
    llm_config: dict,
) -> list[AnalyzedItem]:
    if not items:
        return []

    client = OpenAI(
        api_key=llm_config["api_key"],
        base_url=llm_config.get("base_url") or None,
    )
    model = llm_config["model"]
    batch_size = llm_config.get("batch_size", 6)

    analyzed: list[AnalyzedItem] = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        for item in batch:
            prompt_path = PROMPT_MAP.get(item.source_type, "prompts/blog_prompt.md")
            system_prompt = _load_prompt(prompt_path)
            user_message = _build_user_message(item)

            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=llm_config.get("max_output_tokens", 500),
                    temperature=0.3,
                )
                text = resp.choices[0].message.content or ""
                parsed = _parse_llm_response(text)

                score = float(parsed.get("score", 5.0))
                score = max(0, min(10, score))

                rec_str = parsed.get("recommendation", "optional")
                try:
                    rec = Recommendation(rec_str)
                except ValueError:
                    rec = Recommendation.OPTIONAL

                analyzed.append(AnalyzedItem(
                    title=item.title,
                    url=item.url,
                    source_type=item.source_type,
                    published_at=item.published_at,
                    extra=item.extra,
                    analysis=parsed.get("analysis", ""),
                    score=score,
                    recommendation=rec,
                ))
            except Exception as e:
                logger.error(f"LLM analysis failed for {item.url}: {e}")
                analyzed.append(AnalyzedItem(
                    title=item.title,
                    url=item.url,
                    source_type=item.source_type,
                    published_at=item.published_at,
                    extra=item.extra,
                    analysis=f"[分析失败: {e}]",
                    score=3.0,
                    recommendation=Recommendation.OPTIONAL,
                ))

    return analyzed


def generate_top_line(
    analyzed_items: list[AnalyzedItem],
    llm_config: dict,
) -> str:
    if not analyzed_items:
        return "今日暂无重要更新。"

    client = OpenAI(
        api_key=llm_config["api_key"],
        base_url=llm_config.get("base_url") or None,
    )
    model = llm_config["model"]
    system_prompt = _load_prompt("prompts/summary_prompt.md")

    item_summaries = []
    for item in analyzed_items[:15]:
        item_summaries.append(f"- [{item.source_type.value}] {item.title}: {item.analysis[:80]}")

    user_message = "今日条目：\n" + "\n".join(item_summaries)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Top line generation failed: {e}")
        return f"今日共 {len(analyzed_items)} 条更新。"


def build_digest(
    analyzed_items: list[AnalyzedItem],
    llm_config: dict,
) -> Digest:
    ranked = rank_items(analyzed_items)
    top_line = generate_top_line(ranked, llm_config)
    sections = group_by_category(ranked, top_n=3)

    must_read = [i for i in ranked if i.recommendation == Recommendation.MUST_READ]
    monitor = [i for i in ranked if i.recommendation == Recommendation.RECOMMENDED]
    optional = [i for i in ranked if i.recommendation == Recommendation.OPTIONAL]

    return Digest(
        date=datetime.now().strftime("%Y-%m-%d"),
        top_line=top_line,
        sections=sections,
        must_read=must_read[:5],
        monitor=monitor[:5],
        optional=optional[:5],
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_processor.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add processor.py tests/test_processor.py
git commit -m "feat: add processor with dedup, LLM analysis, scoring, and digest building"
```

---

### Task 8: Formatter (Feishu Card + Markdown)

**Files:**
- Create: `formatter.py`
- Test: `tests/test_formatter.py`

- [ ] **Step 1: Create `tests/test_formatter.py`**

```python
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
    assert "config" in card
    assert "header" in card["config"]
    elements = card["config"]["body"]["contents"]
    assert any("今日推荐" in str(e) for e in elements)
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
    assert "## 论文" in md
    assert "Paper1" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_formatter.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Create `formatter.py`**

```python
from __future__ import annotations
from models import Digest, AnalyzedItem, Recommendation, CategorySection

REC_LABELS = {
    Recommendation.MUST_READ: "⭐必读",
    Recommendation.RECOMMENDED: "👍推荐",
    Recommendation.MONITOR: "👁️待关注",
    Recommendation.OPTIONAL: "📌可选",
}


def _item_to_feishu_elements(item: AnalyzedItem) -> list[dict]:
    elements = []
    elements.append({
        "tag": "markdown",
        "content": f"**[{item.title}]({item.url})**",
    })
    rec_label = REC_LABELS.get(item.recommendation, "")
    analysis_lines = item.analysis.split("\n") if item.analysis else []
    content_parts = [f"{rec_label} 评分: {item.score}/10"]
    content_parts.extend(analysis_lines)
    elements.append({
        "tag": "markdown",
        "content": "\n".join(content_parts),
    })
    elements.append({"tag": "hr"})
    return elements


def build_feishu_card(digest: Digest) -> dict:
    elements = []
    elements.append({
        "tag": "markdown",
        "content": f"**📌 今日摘要**\n{digest.top_line}",
    })
    elements.append({"tag": "hr"})

    for section in digest.sections:
        if not section.items:
            continue
        elements.append({
            "tag": "markdown",
            "content": f"**{section.icon} {section.category}**",
        })
        for item in section.items:
            elements.extend(_item_to_feishu_elements(item))

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": "**🎯 今日推荐**",
    })
    if digest.must_read:
        for item in digest.must_read[:3]:
            elements.append({
                "tag": "markdown",
                "content": f"- [{item.title}]({item.url}) {REC_LABELS.get(item.recommendation, '')}",
            })
    else:
        elements.append({"tag": "markdown", "content": "- 今日无必读项"})

    if digest.monitor:
        elements.append({"tag": "markdown", "content": "**👁️ 待关注**"})
        for item in digest.monitor[:3]:
            elements.append({
                "tag": "markdown",
                "content": f"- [{item.title}]({item.url})",
            })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"☁️ 每日云原生速递 {digest.date}",
                    },
                    "template": "blue",
                },
                "body": {
                    "contents": elements,
                },
            },
        },
    }


def _item_to_markdown(item: AnalyzedItem) -> str:
    rec_label = REC_LABELS.get(item.recommendation, "")
    lines = [
        f"### [{item.title}]({item.url})",
        f"**推荐**: {rec_label} | **评分**: {item.score}/10",
        "",
        item.analysis or "",
        "",
    ]
    return "\n".join(lines)


def build_markdown(digest: Digest) -> str:
    lines = [
        f"# 每日云原生速递 {digest.date}",
        "",
        f"> {digest.top_line}",
        "",
    ]

    for section in digest.sections:
        if not section.items:
            continue
        lines.append(f"## {section.icon} {section.category}")
        lines.append("")
        for item in section.items:
            lines.append(_item_to_markdown(item))

    lines.append("## 🎯 今日推荐")
    lines.append("")
    if digest.must_read:
        for i, item in enumerate(digest.must_read[:3], 1):
            lines.append(f"{i}. [{item.title}]({item.url})")
    else:
        lines.append("今日无必读项。")

    if digest.monitor:
        lines.append("")
        lines.append("## 👁️ 待关注")
        lines.append("")
        for item in digest.monitor[:3]:
            lines.append(f"- [{item.title}]({item.url})")

    if digest.optional:
        lines.append("")
        lines.append("## 📌 可忽略")
        lines.append("")
        for item in digest.optional[:3]:
            lines.append(f"- [{item.title}]({item.url})")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by Daily Cloud Native Briefing on {digest.date}*")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_formatter.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add formatter.py tests/test_formatter.py
git commit -m "feat: add Feishu Interactive Card and Markdown formatter"
```

---

### Task 9: Feishu Notifier

**Files:**
- Create: `notifier.py`

- [ ] **Step 1: Create `notifier.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add notifier.py
git commit -m "feat: add Feishu notifier with retry"
```

---

### Task 10: GitHub Archiver

**Files:**
- Create: `archiver.py`

- [ ] **Step 1: Create `archiver.py`**

```python
from __future__ import annotations
import logging
import subprocess
from pathlib import Path
from models import Digest
from formatter import build_markdown

logger = logging.getLogger(__name__)


def archive_to_github(digest: Digest, config: dict) -> bool:
    try:
        repo_path = config.get("repo_path", ".")
        content_dir = config.get("content_dir", "content")
        remote = config.get("remote", "origin")
        branch = config.get("branch", "main")

        content_path = Path(repo_path) / content_dir
        content_path.mkdir(parents=True, exist_ok=True)

        md_content = build_markdown(digest)
        md_file = content_path / f"{digest.date}.md"
        md_file.write_text(md_content, encoding="utf-8")

        logger.info(f"Markdown written to {md_file}")

        subprocess.run(
            ["git", "-C", repo_path, "add", str(md_file.relative_to(repo_path))],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", f"daily: {digest.date} cloud native briefing"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", repo_path, "push", remote, branch],
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info(f"Archived to GitHub: {digest.date}.md")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Archive failed: {e}")
        return False
```

- [ ] **Step 2: Commit**

```bash
git add archiver.py
git commit -m "feat: add GitHub archiver with auto commit and push"
```

---

### Task 11: Main Orchestrator

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
from __future__ import annotations
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from config_loader import load_config
from models import RawItem, SourceType
from processor import dedup_items, load_prev_urls, analyze_items, build_digest
from collectors.github import GitHubCollector
from collectors.cncf import CNCFCollector
from collectors.arxiv import ArXivCollector
from collectors.blogs import BlogsCollector
from collectors.wechat import WeChatCollector
from notifier import send_to_feishu
from archiver import archive_to_github


def setup_logging(date_str: str) -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{date_str}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("main")


async def run_collectors(config: dict, logger: logging.Logger) -> list[RawItem]:
    collectors = [
        GitHubCollector(config["sources"]["github"]),
        CNCFCollector(config["sources"]["cncf"]),
        ArXivCollector(config["sources"]["arxiv"]),
        BlogsCollector(config["sources"]["blogs"]),
        WeChatCollector(config["sources"]["wechat"]),
    ]

    all_items: list[RawItem] = []
    tasks = []
    for c in collectors:
        tasks.append(_safe_collect(c, logger))

    results = await asyncio.gather(*tasks)
    for items in results:
        all_items.extend(items)

    logger.info(f"Total raw items collected: {len(all_items)}")
    return all_items


async def _safe_collect(collector, logger: logging.Logger) -> list[RawItem]:
    try:
        items = await asyncio.wait_for(collector.collect(), timeout=60)
        logger.info(f"{collector.source_name}: collected {len(items)} items")
        return items
    except asyncio.TimeoutError:
        logger.error(f"{collector.source_name}: timed out after 60s")
        return []
    except Exception as e:
        logger.error(f"{collector.source_name}: failed - {e}")
        return []


def save_raw_data(items: list[RawItem], data_dir: str, date_str: str):
    data_path = Path(data_dir)
    data_path.mkdir(exist_ok=True)
    file_path = data_path / f"{date_str}.json"
    data = {
        "date": date_str,
        "raw_items": [
            {**item.model_dump(), "published_at": item.published_at.isoformat()}
            for item in items
        ],
    }
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    logger = setup_logging(date_str)
    logger.info(f"=== Daily Cloud Native Briefing {date_str} ===")

    config = load_config()

    raw_items = await run_collectors(config, logger)
    save_raw_data(raw_items, "data", date_str)

    prev_urls = load_prev_urls("data")
    deduped = dedup_items(raw_items, prev_urls)
    logger.info(f"After dedup: {len(deduped)} items")

    analyzed = analyze_items(deduped, config["llm"])
    logger.info(f"Analyzed: {len(analyzed)} items")

    digest = build_digest(analyzed, config["llm"])
    logger.info(f"Digest built: {len(digest.sections)} sections")

    success = await send_to_feishu(digest, config["feishu"]["webhook_url"])
    if not success:
        logger.error("Feishu push failed")

    if "github_archive" in config:
        archive_to_github(digest, config["github_archive"])

    logger.info("=== Briefing complete ===")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add main orchestrator with full pipeline"
```

---

### Task 12: Integration Test and Final Verification

**Files:**
- Test: `tests/test_integration.py`

- [ ] **Step 1: Create `tests/test_integration.py`**

```python
from datetime import datetime, timezone
from models import RawItem, AnalyzedItem, SourceType, Recommendation, Digest
from processor import dedup_items, rank_items, group_by_category, build_digest
from formatter import build_feishu_card, build_markdown


def test_full_pipeline_dedup_to_digest():
    items = [
        RawItem(
            title="K8s 1.32 Release",
            url="https://kubernetes.io/blog/1.32",
            source_type=SourceType.CNCF,
            content="Kubernetes 1.32 includes significant scheduling improvements.",
        ),
        RawItem(
            title="vLLM Performance Paper",
            url="https://arxiv.org/abs/test1",
            source_type=SourceType.ARXIV,
            content="We propose a new PagedAttention mechanism that improves throughput by 2x.",
            extra={"authors": ["Alice"], "categories": ["cs.DC"]},
        ),
        RawItem(
            title="Cilium eBPF Gateway",
            url="https://github.com/cilium/cilium",
            source_type=SourceType.GITHUB,
            content="Cilium now supports Gateway API with eBPF data plane.",
            extra={"stars": 20000},
        ),
    ]

    deduped = dedup_items(items)
    assert len(deduped) == 3

    mock_analyzed = [
        AnalyzedItem(
            title=item.title,
            url=item.url,
            source_type=item.source_type,
            published_at=datetime.now(timezone.utc),
            extra=item.extra,
            analysis="Great technical advancement.",
            score=8.0 if item.source_type == SourceType.ARXIV else 7.0,
            recommendation=Recommendation.MUST_READ if item.source_type == SourceType.ARXIV else Recommendation.RECOMMENDED,
        )
        for item in deduped
    ]

    digest = Digest(
        date="2026-03-27",
        top_line="vLLM paper and K8s release are highlights.",
        sections=group_by_category(mock_analyzed),
        must_read=[i for i in mock_analyzed if i.recommendation == Recommendation.MUST_READ],
        monitor=[i for i in mock_analyzed if i.recommendation == Recommendation.RECOMMENDED],
        optional=[],
    )

    card = build_feishu_card(digest)
    assert card["msg_type"] == "interactive"

    md = build_markdown(digest)
    assert "# 每日云原生速递" in md
    assert "vLLM" in md
    assert "K8s" in md
    assert "Cilium" in md


def test_empty_items_pipeline():
    digest = Digest(date="2026-03-27", top_line="No updates today.")
    card = build_feishu_card(digest)
    assert card["msg_type"] == "interactive"

    md = build_markdown(digest)
    assert "2026-03-27" in md
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full pipeline"
```

---

### Task 13: Install Dependencies and Smoke Test

- [ ] **Step 1: Create virtual environment and install dependencies**

Run:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

- [ ] **Step 2: Copy `.env.example` to `.env` and fill in real values**

Run:
```bash
copy .env.example .env
```

Edit `.env` with actual API keys.

- [ ] **Step 3: Run main.py with real config**

Run:
```bash
python main.py
```

Expected: Logs show collector results, LLM analysis, Feishu push status, and GitHub archive status.

- [ ] **Step 4: Verify Feishu message received**

Check the Feishu group for the Interactive Card message.

- [ ] **Step 5: Verify GitHub commit**

Run:
```bash
git log --oneline -3
```

Expected: A commit with message `daily: 2026-03-27 cloud native briefing` and `content/2026-03-27.md` file.

- [ ] **Step 6: Commit final state**

```bash
git add -A
git commit -m "chore: project ready for daily scheduling"
```

---

### Task 14: Windows Task Scheduler Setup

- [ ] **Step 1: Create a batch script `run_daily.bat`**

```bat
@echo off
cd /d D:\lihangyu\2026\2026Q1\每日云原生
.venv\Scripts\python.exe main.py >> logs\scheduler.log 2>&1
```

- [ ] **Step 2: Register Windows Task Scheduler job**

Run in PowerShell as Administrator:
```powershell
$action = New-ScheduledTaskAction -Execute "D:\lihangyu\2026\2026Q1\每日云原生\run_daily.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "DailyCloudNativeBriefing" -Action $action -Trigger $trigger -Settings $settings -Description "Daily Cloud Native Briefing to Feishu and GitHub"
```

- [ ] **Step 3: Verify the scheduled task exists**

Run:
```powershell
Get-ScheduledTask -TaskName "DailyCloudNativeBriefing"
```

Expected: Task is listed and enabled.

- [ ] **Step 4: Commit batch script**

```bash
git add run_daily.bat
git commit -m "chore: add Windows Task Scheduler batch script"
```
