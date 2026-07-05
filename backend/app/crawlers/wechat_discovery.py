"""公众号浏览器挖掘 Provider。"""
from __future__ import annotations

import logging

from app.crawlers.base import CrawlerProvider, JobPosting
from app.services.wechat_discovery import run_wechat_discovery_pipeline

logger = logging.getLogger(__name__)


class WechatDiscoveryProvider(CrawlerProvider):
    name = "wechat_discovery"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher=None,
    ) -> list[JobPosting]:
        config = config or {}
        jobs, reports = await run_wechat_discovery_pipeline(config)
        for r in reports:
            logger.info(
                "wechat_discovery step %s %s: %s count=%s",
                r.get("step"),
                r.get("name"),
                r.get("status"),
                r.get("count"),
            )
        return jobs
