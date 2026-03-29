# 修复 ArXiv 和 WeChat 数据源采集

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 ArXiv 和 WeChat 数据源能够正常采集内容

**Architecture:** 
- ArXiv: 增加超时时间、添加重试机制、优化查询条件避免 429 限流
- WeChat: 改用公众号 biz ID 方式，提供配置映射表

**Tech Stack:** Python, httpx, RSSHub

---

## 问题分析

### ArXiv 问题
1. 超时时间只有 30 秒，arXiv API 响应慢
2. 查询使用 OR 逻辑组合 categories 和 keywords，导致查询太复杂
3. 没有 429 限流处理和重试机制

### WeChat 问题
1. 当前路由 `/wechat/mp/article/{account}` 在 RSSHub 中不存在
2. RSSHub 支持的路由需要公众号的 `biz` ID（Base64 编码的公众号标识）
3. 配置中只提供了账号名，无法直接使用

---

## File Structure

```
每日云原生/
├── collectors/
│   ├── arxiv.py          # 修改: 增加超时、重试机制
│   └── wechat.py         # 修改: 改用 biz ID 映射方式
├── config.yaml           # 修改: 更新 wechat 配置格式
└── run_daily.bat         # 修改: 启动前检查 RSSHub
```

---

## Task 1: 修复 ArXiv Collector

**Files:**
- Modify: `collectors/arxiv.py`

**问题:** 超时 30 秒太短，没有重试机制，查询条件过于复杂导致 429

- [ ] **Step 1: 修改 arxiv.py 增加超时和重试机制**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import httpx
import xml.etree.ElementTree as ET
from models import RawItem, SourceType
from collectors.base import BaseCollector

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
logger = logging.getLogger(__name__)


class ArXivCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "arxiv"

    async def collect(self) -> list[RawItem]:
        categories = self.config.get("categories", ["cs.DC"])
        keywords = self.config.get("keywords", [])
        max_results = self.config.get("max_results", 20)
        timeout = self.config.get("timeout", 120)

        # 只按分类查询，避免 OR 组合导致查询过宽
        query_parts = [f"cat:{cat}" for cat in categories[:3]]
        query = " OR ".join(query_parts)

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        items = []
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(
                        "https://export.arxiv.org/api/query",
                        params=params
                    )
                    if resp.status_code == 429:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"arxiv: rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                    resp.raise_for_status()
                    items = self._parse_response(resp.text)
                    break
            except httpx.TimeoutException:
                logger.warning(f"arxiv: timeout on attempt {attempt + 1}/3")
                if attempt < 2:
                    await asyncio.sleep(10)
                else:
                    logger.error("arxiv: all retries exhausted")
            except Exception as e:
                logger.error(f"arxiv: failed - {e}")
                break

        return items

    def _parse_response(self, xml_text: str) -> list[RawItem]:
        root = ET.fromstring(xml_text)
        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

        for entry in root.findall("atom:entry", ARXIV_NS):
            published_el = entry.find("atom:published", ARXIV_NS)
            if published_el is None:
                continue
            published_str = published_el.text
            published = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            if published < cutoff:
                continue

            title_el = entry.find("atom:title", ARXIV_NS)
            title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
            id_el = entry.find("atom:id", ARXIV_NS)
            link = id_el.text if id_el is not None else ""
            summary_el = entry.find("atom:summary", ARXIV_NS)
            summary = summary_el.text.strip().replace("\n", " ") if summary_el is not None else ""
            authors = [
                a.find("atom:name", ARXIV_NS).text
                for a in entry.findall("atom:author", ARXIV_NS)
                if a.find("atom:name", ARXIV_NS) is not None
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

- [ ] **Step 2: 测试 ArXiv collector**

```bash
cd "D:/lihangyu/2026/2026Q1/每日云原生" && ".venv/Scripts/python.exe" -c "
import asyncio
from collectors.arxiv import ArXivCollector
from config_loader import load_config

config = load_config('config.yaml')
collector = ArXivCollector(config['sources']['arxiv'])
items = asyncio.run(collector.collect())
print(f'Collected {len(items)} items from arxiv')
if items:
    print(f'First item: {items[0].title[:50]}...')
"
```

---

## Task 2: 重构 WeChat Collector

**Files:**
- Modify: `collectors/wechat.py`
- Modify: `config.yaml`

**问题:** RSSHub 没有按账号名查询的路由，需要使用 biz ID

- [ ] **Step 1: 更新 config.yaml 中的 wechat 配置**

将 wechat 配置从账号名改为 biz ID 映射：

```yaml
  wechat:
    rsshub_url: "http://localhost:1200"
    # 公众号配置: name 为显示名称, biz 为公众号 ID (从分享链接获取)
    # 获取方法: 从公众号分享的链接中提取 __biz 参数
    accounts:
      - name: "云原生实验室"
        biz: "MzIwMjIxNTE4MA=="
      - name: "KubeSphere"
        biz: "MzUzNzA0NTY1Ng=="
      - name: "DaoCloud"
        biz: "MzA4ODI4MDY4MA=="
```

- [ ] **Step 2: 重写 wechat.py 使用 biz ID**

```python
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
import httpx
import xml.etree.ElementTree as ET
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
        hours = self.config.get("hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        async with httpx.AsyncClient(timeout=30) as client:
            for account in self.accounts:
                name = account.get("name", "Unknown")
                biz = account.get("biz", "")
                if not biz:
                    logger.warning(f"wechat: skipping {name}, no biz ID configured")
                    continue

                # 使用 /wechat/mp/homepage/:biz 路由
                # hid=0 表示最新文章列表
                feed_url = f"{self.rsshub_url}/wechat/mp/homepage/{biz}/0"

                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        logger.warning(f"wechat: {name} returned {resp.status_code}")
                        continue

                    account_items = self._parse_rss(resp.text, name, cutoff)
                    items.extend(account_items)
                    logger.info(f"wechat: {name} collected {len(account_items)} items")
                except Exception as e:
                    logger.error(f"wechat: {name} failed - {e}")

        return items

    def _parse_rss(self, rss_text: str, account_name: str, cutoff: datetime) -> list[RawItem]:
        items = []
        try:
            root = ET.fromstring(rss_text)
            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pubDate_el = item.find("pubDate")
                desc_el = item.find("description")

                title = title_el.text if title_el is not None else ""
                link = link_el.text if link_el is not None else ""

                published = None
                if pubDate_el is not None and pubDate_el.text:
                    try:
                        published = datetime.strptime(
                            pubDate_el.text, "%a, %d %b %Y %H:%M:%S %Z"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        published = datetime.now(timezone.utc)

                if published and published < cutoff:
                    continue

                content = desc_el.text if desc_el is not None else ""

                items.append(RawItem(
                    title=title,
                    url=link,
                    source_type=SourceType.WECHAT,
                    content=content[:1000] if content else "",
                    published_at=published or datetime.now(timezone.utc),
                    extra={
                        "account": account_name,
                    },
                ))
        except ET.ParseError as e:
            logger.error(f"wechat: RSS parse error - {e}")

        return items
```

- [ ] **Step 3: 测试 WeChat collector (需要先启动 RSSHub)**

```bash
cd "D:/lihangyu/2026/2026Q1/每日云原生" && ".venv/Scripts/python.exe" -c "
import asyncio
from collectors.wechat import WeChatCollector
from config_loader import load_config

config = load_config('config.yaml')
collector = WeChatCollector(config['sources']['wechat'])
items = asyncio.run(collector.collect())
print(f'Collected {len(items)} items from wechat')
"
```

---

## Task 3: 更新启动脚本确保 RSSHub 运行

**Files:**
- Modify: `run_daily.bat`

- [ ] **Step 1: 更新 run_daily.bat 添加 RSSHub 检查**

```batch
@echo off
cd /d D:\lihangyu\2026\2026Q1\每日云原生

REM Check if RSSHub is running
curl -s -o nul -w "" http://localhost:1200 2>nul
if errorlevel 1 (
    echo [%date% %time%] Starting RSSHub...
    start /b cmd /c "cd /d D:\lihangyu\xcode\opencode-playground\RSSHub && npm start > nul 2>&1"
    timeout /t 10 /nobreak > nul
)

.venv\Scripts\python.exe main.py >> logs\scheduler.log 2>&1
```

---

## Task 4: 获取真实公众号的 biz ID

**说明:** biz ID 需要从微信公众号的历史文章页面 URL 中提取

- [ ] **Step 1: 提供获取 biz ID 的说明文档**

在 `config.yaml` 中添加注释说明如何获取 biz ID：

```yaml
  # wechat 公众号配置说明:
  # 1. 在微信中打开公众号，点击右上角查看历史消息
  # 2. 复制分享链接，格式类似:
  #    https://mp.weixin.qq.com/mp/homepage?__biz=MzIwMjIxNTE4MA==&hid=0
  # 3. 提取 __biz= 后面的值 (到 & 之前)，这就是 biz ID
  # 4. 如果链接中没有 __biz，可以使用以下方法:
  #    - 在公众号文章页面，查看源代码搜索 var biz
  #    - 或使用浏览器开发者工具查看网络请求中的 biz 参数
```

---

## Task 5: 完整测试

- [ ] **Step 1: 确保 RSSHub 运行**

```bash
curl http://localhost:1200
```

预期: 返回 RSSHub 欢迎页面

- [ ] **Step 2: 测试完整流程 (dry-run)**

```bash
cd "D:/lihangyu/2026/2026Q1/每日云原生" && ".venv/Scripts/python.exe" main.py --dry-run
```

预期: ArXiv 和 WeChat 都能采集到数据

- [ ] **Step 3: 提交代码**

```bash
git add collectors/arxiv.py collectors/wechat.py config.yaml run_daily.bat
git commit -m "fix: improve arxiv retry mechanism and refactor wechat to use biz ID"
```

---

## 备选方案: 如果 biz ID 无法获取

如果无法获取公众号的 biz ID，可以使用以下备选方案：

### 方案 A: 使用搜狗微信搜索
RSSHub 有 `/wechat/sogou/{keyword}` 路由，可以按关键词搜索微信公众号文章

### 方案 B: 暂时禁用微信源
运行时加 `--skip-wechat` 参数

### 方案 C: 使用公共 RSSHub 实例
修改 `rsshub_url` 为 `https://rsshub.app`，但公共实例可能有频率限制
