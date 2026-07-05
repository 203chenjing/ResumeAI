"""27届提前批/校招 curated 页面 Provider。"""
from __future__ import annotations

import logging
import uuid

import httpx

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.crawl_config import get_compliance
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.parsers import parse_early_batch_html

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def _fetch_early_batch_html(url: str, source: dict, fetcher: CrawlFetcher) -> tuple[str, str]:
    """优先 httpx（避免 Playwright 403），必要时再 Playwright。"""
    prefer_httpx = source.get("prefer_httpx", True)
    if prefer_httpx:
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers={"User-Agent": BROWSER_UA}) as http:
                resp = await http.get(url)
                resp.raise_for_status()
                if len(resp.text) > 500 and "403 Forbidden" not in resp.text[:200]:
                    return resp.text, str(resp.url)
        except Exception as e:
            logger.warning("early_batch httpx failed %s: %s", url[:60], e)

    page = await fetcher.fetch(
        url,
        use_playwright=bool(source.get("use_playwright", False)),
        ignore_robots=bool(source.get("ignore_robots", True)),
        wait_ms=int(source.get("wait_ms", 3000)),
        timeout=float(source.get("timeout", 60)),
    )
    return page.html or page.text or "", page.url or url


class EarlyBatchProvider(CrawlerProvider):
    name = "early_batch"

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

        jobs: list[JobPosting] = []
        for source in config.get("sources") or []:
            if source.get("enabled") is False:
                continue
            url = source.get("list_url") or source.get("url", "")
            if not url:
                continue
            sid = source.get("id", url)
            try:
                html, final_url = await _fetch_early_batch_html(url, source, fetcher)
                items = parse_early_batch_html(
                    html,
                    source_id=sid,
                    source_name=source.get("name", sid),
                    channel=source.get("channel", "27届提前批"),
                    base_url=final_url,
                    tags=list(source.get("tags") or ["27届", "提前批", "校招"]),
                    max_items=int(source.get("max_items", 60)),
                )
                logger.info("early_batch %s: %d jobs", sid, len(items))
                jobs.extend(items)
            except Exception as e:
                logger.warning("early_batch %s failed: %s", sid, e)

        if own_fetcher:
            await fetcher.close()
        return jobs
