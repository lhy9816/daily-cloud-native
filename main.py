from __future__ import annotations
import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from config_loader import load_config
from models import RawItem
from processor import dedup_items, load_prev_urls, analyze_items, build_digest
from collectors.github import GitHubCollector
from collectors.cncf import CNCFCollector
from collectors.arxiv import ArXivCollector
from collectors.blogs import BlogsCollector
from collectors.tech_media import TechMediaCollector
from notifier import send_to_feishu
from archiver import archive_to_github


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Cloud Native Briefing")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub collector")
    parser.add_argument("--no-github-token", action="store_true", help="Run GitHub collector without token auth")
    parser.add_argument("--skip-cncf", action="store_true", help="Skip CNCF collector")
    parser.add_argument("--skip-arxiv", action="store_true", help="Skip ArXiv collector")
    parser.add_argument("--skip-blogs", action="store_true", help="Skip blogs collector")
    parser.add_argument("--skip-tech-media", action="store_true", help="Skip tech media collector (36kr/zhihu)")
    parser.add_argument("--skip-feishu", action="store_true", help="Skip Feishu push")
    parser.add_argument("--skip-archive", action="store_true", help="Skip GitHub archive")
    parser.add_argument("--dry-run", action="store_true", help="Collect and analyze only, no push")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    return parser.parse_args()


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


async def run_collectors(config: dict, logger: logging.Logger, args: argparse.Namespace) -> list[RawItem]:
    collectors = []
    if not args.skip_github:
        gh_config = config["sources"]["github"]
        if args.no_github_token:
            gh_config = {**gh_config, "token": ""}
        collectors.append(GitHubCollector(gh_config))
    if not args.skip_cncf:
        collectors.append(CNCFCollector(config["sources"]["cncf"]))
    if not args.skip_arxiv:
        collectors.append(ArXivCollector(config["sources"]["arxiv"]))
    if not args.skip_blogs:
        collectors.append(BlogsCollector(config["sources"]["blogs"]))
    if not args.skip_tech_media and "tech_media" in config["sources"]:
        collectors.append(TechMediaCollector(config["sources"]["tech_media"]))

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
    args = parse_args()
    logger = setup_logging(date_str)
    logger.info(f"=== Daily Cloud Native Briefing {date_str} ===")

    config = load_config(args.config)

    if not args.dry_run or not args.skip_feishu:
        _validate_llm_key(config["llm"], logger)

    if not args.dry_run:
        _validate_feishu_webhook(config["feishu"]["webhook_url"], logger)

    raw_items = await run_collectors(config, logger, args)
    save_raw_data(raw_items, "data", date_str)

    prev_urls = load_prev_urls("data")
    deduped = dedup_items(raw_items, prev_urls)
    logger.info(f"After dedup: {len(deduped)} items")

    analyzed = analyze_items(deduped, config["llm"])
    logger.info(f"Analyzed: {len(analyzed)} items")

    digest = build_digest(analyzed, config["llm"])
    logger.info(f"Digest built: {len(digest.sections)} sections")

    if args.dry_run:
        logger.info("Dry run mode - skipping push and archive")
        return

    if not args.skip_feishu:
        success = await send_to_feishu(digest, config["feishu"]["webhook_url"])
        if not success:
            logger.error("Feishu push failed")

    if not args.skip_archive and "github_archive" in config:
        archive_to_github(digest, config["github_archive"])

    logger.info("=== Briefing complete ===")


def _validate_llm_key(llm_config: dict, logger: logging.Logger):
    from openai import OpenAI
    client = OpenAI(
        api_key=llm_config["api_key"],
        base_url=llm_config.get("base_url") or None,
    )
    try:
        resp = client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        logger.info(f"LLM API key validated, model: {llm_config['model']}")
    except Exception as e:
        logger.error(f"LLM API key validation FAILED: {e}")
        logger.error("Please check your LLM_API_KEY in .env file")
        sys.exit(1)


def _validate_feishu_webhook(webhook_url: str, logger: logging.Logger):
    if not webhook_url or webhook_url.startswith("${"):
        logger.error("Feishu webhook URL not configured. Please set FEISHU_WEBHOOK_URL in .env")
        sys.exit(1)
    if not webhook_url.startswith("https://open.feishu.cn"):
        logger.warning(f"Feishu webhook URL looks unusual: {webhook_url[:50]}...")


if __name__ == "__main__":
    asyncio.run(main())

