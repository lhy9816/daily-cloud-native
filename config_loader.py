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
