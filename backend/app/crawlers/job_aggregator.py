"""公开求职聚合站 Provider：牛客、24365、北京高校平台。"""
from __future__ import annotations

import logging

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.crawl_config import get_compliance
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.parsers import parse_source_page

logger = logging.getLogger(__name__)


class JobAggregatorProvider(CrawlerProvider):
    name = "job_aggregator"

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
            fetcher = CrawlFetcher(get_compliance())

        sources = list(config.get("sources") or [])
        jobs: list[JobPosting] = []

        for source in sources:
            if source.get("enabled") is False:
                continue
            sid = source.get("id", "")
            try:
                items = await parse_source_page(fetcher, source, self.name)
                logger.info("job_aggregator %s: %d jobs", sid, len(items))
                jobs.extend(items)
            except Exception as e:
                logger.warning("job_aggregator %s failed: %s", sid, e)

        if own_fetcher:
            await fetcher.close()
        return jobs
