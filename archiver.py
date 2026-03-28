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
        try:
            subprocess.run(
                ["git", "-C", repo_path, "push", remote, branch],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git push failed (remote may not be configured): {e.stderr.strip()}")
            return True

        logger.info(f"Archived to GitHub: {digest.date}.md")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Archive failed: {e}")
        return False
