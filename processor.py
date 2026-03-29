from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
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
    SourceType.TECH_MEDIA: ("科技媒体", "📰"),
}

PROMPT_MAP = {
    SourceType.ARXIV: "prompts/paper_prompt.md",
    SourceType.GITHUB: "prompts/github_prompt.md",
    SourceType.BLOG: "prompts/blog_prompt.md",
    SourceType.TECH_MEDIA: "prompts/blog_prompt.md",
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

    for item in items:
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
