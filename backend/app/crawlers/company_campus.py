"""企业校招页 Provider（L2）：读取 crawl_sources.yml，支持 Playwright 解析 SPA。"""
from __future__ import annotations

import logging
import uuid

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.parsers import parse_source_page

logger = logging.getLogger(__name__)


class CompanyCampusProvider(CrawlerProvider):
    name = "company_campus"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: CrawlFetcher | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        if not config.get("enabled", True):
            return []

        own_fetcher = fetcher is None
        if own_fetcher:
            from app.crawlers.crawl_config import get_compliance

            fetcher = CrawlFetcher(get_compliance())

        sources = list(config.get("sources") or [])
        for legacy in config.get("companies") or []:
            if isinstance(legacy, dict) and legacy.get("list_url"):
                sources.append(legacy)

        jobs: list[JobPosting] = []
        for source in sources:
            if source.get("enabled") is False:
                continue
            sid = source.get("id", source.get("list_url", ""))
            try:
                items = await parse_source_page(fetcher, source, self.name)
                logger.info("company_campus source %s: %d jobs", sid, len(items))
                jobs.extend(items)
            except Exception as e:
                logger.warning("company_campus source %s failed: %s", sid, e)

        if own_fetcher:
            await fetcher.close()
        return jobs
