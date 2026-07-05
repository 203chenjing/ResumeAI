"""浏览器模拟人操作 Provider（五步流水线）。"""
from __future__ import annotations

import logging

from app.crawlers.base import CrawlerProvider, JobPosting
from app.services.browser_discovery import run_browser_discovery_pipeline

logger = logging.getLogger(__name__)


class BrowserDiscoveryProvider(CrawlerProvider):
    name = "browser_discovery"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: object | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        jobs, reports = await run_browser_discovery_pipeline(config)
        for r in reports:
            logger.info(
                "browser_discovery step %s %s: %s count=%s",
                r.get("step"),
                r.get("name"),
                r.get("status"),
                r.get("count"),
            )
        return jobs
