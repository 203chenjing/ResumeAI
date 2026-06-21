"""高校就业网 Provider（L1）：读取 crawl_sources.yml，Playwright 渲染后解析。"""
from __future__ import annotations

import logging
import uuid

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.parsers import parse_source_page

logger = logging.getLogger(__name__)

# 仅当 crawl_sources.yml 设置 fallback_seeds: true 且全部源失败时使用
SEED_JOBS = [
    {
        "id": "seed-tsinghua",
        "name": "清华大学",
        "list_url": "http://career.cic.tsinghua.edu.cn/xsglxt/f/jyxt/anony/xxfb",
        "parser": "generic_list",
        "channel": "高校就业网",
        "tags": ["校招", "清华"],
        "use_playwright": True,
        "wait_ms": 3000,
    },
]


class UniversityHtmlProvider(CrawlerProvider):
    name = "university_html"

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
        # 兼容旧版 urls: [{url, school}]
        for legacy in config.get("urls") or []:
            if isinstance(legacy, str):
                sources.append({"id": uuid.uuid4().hex[:8], "name": config.get("school", "高校就业网"), "list_url": legacy})
            elif isinstance(legacy, dict):
                sources.append(
                    {
                        "id": legacy.get("id", uuid.uuid4().hex[:8]),
                        "name": legacy.get("school", config.get("school", "高校就业网")),
                        "list_url": legacy.get("url", ""),
                        "parser": legacy.get("parser", "generic_list"),
                    }
                )

        if not sources and config.get("fallback_seeds"):
            sources = SEED_JOBS

        jobs: list[JobPosting] = []
        errors: list[str] = []

        for source in sources:
            if source.get("enabled") is False:
                continue
            sid = source.get("id", source.get("list_url", ""))
            try:
                items = await parse_source_page(fetcher, source, self.name)
                logger.info("university_html source %s: %d jobs", sid, len(items))
                jobs.extend(items)
            except Exception as e:
                msg = f"{sid}: {e}"
                logger.warning("university_html failed %s", msg)
                errors.append(msg)

        if own_fetcher:
            await fetcher.close()

        if not jobs:
            logger.error("university_html no jobs; errors=%s", errors)
        return jobs
