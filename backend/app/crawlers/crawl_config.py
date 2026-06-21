"""加载 crawl_sources.yml 配置。"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "crawl_sources.yml"

DEFAULT_CONFIG: dict[str, Any] = {
    "providers": {},
    "compliance": {
        "respect_robots": True,
        "rate_limit_rps": 0.5,
        "public_pages_only": True,
        "user_agent": "ResumeAI-Crawler/1.0 (campus-job-aggregator; +https://github.com)",
    },
}


@lru_cache(maxsize=1)
def load_crawl_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        logger.warning("crawl_sources.yml not found at %s", CONFIG_PATH)
        return dict(DEFAULT_CONFIG)
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        merged = dict(DEFAULT_CONFIG)
        merged.update({k: v for k, v in raw.items() if k != "providers" and k != "compliance"})
        merged["compliance"] = {**DEFAULT_CONFIG["compliance"], **(raw.get("compliance") or {})}
        merged["providers"] = raw.get("providers") or {}
        return merged
    except Exception as e:
        logger.exception("Failed to load crawl_sources.yml: %s", e)
        return dict(DEFAULT_CONFIG)


def get_provider_config(name: str) -> dict[str, Any]:
    cfg = load_crawl_config()
    return cfg.get("providers", {}).get(name) or {}


def get_compliance() -> dict[str, Any]:
    return load_crawl_config().get("compliance") or DEFAULT_CONFIG["compliance"]


def reload_crawl_config() -> dict[str, Any]:
    load_crawl_config.cache_clear()
    return load_crawl_config()
