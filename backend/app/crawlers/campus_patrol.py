"""大厂校招页巡检：检测页面是否出现 27届/2027 关键词并生成岗位条目。"""
from __future__ import annotations

import hashlib
import logging
import re

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.crawl_config import get_compliance
from app.crawlers.fetcher import CrawlFetcher

logger = logging.getLogger(__name__)

COHORT_RE = re.compile(r"27届|2027届|2027\s*届|面向2027|2027\s*graduate", re.I)


class CampusPatrolProvider(CrawlerProvider):
    name = "campus_patrol"

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
            company = source.get("name") or source.get("company") or "未知企业"
            if not url:
                continue
            sid = source.get("id", url)
            try:
                page = await fetcher.fetch(
                    url,
                    use_playwright=bool(source.get("use_playwright", True)),
                    ignore_robots=bool(source.get("ignore_robots", True)),
                    wait_ms=int(source.get("wait_ms", 4000)),
                    timeout=float(source.get("timeout", 90)),
                )
                blob = f"{page.text or ''} {page.html or ''}"
                if not COHORT_RE.search(blob):
                    logger.info("campus_patrol %s: no 27届 signal", sid)
                    continue
                batch = _guess_batch(blob)
                role = batch or "27届校招"
                jid = hashlib.sha256(f"{sid}:{url}".encode()).hexdigest()[:12]
                jobs.append(
                    JobPosting(
                        id=jid,
                        company=company[:60],
                        role=role[:120],
                        source=self.name,
                        jd_text=f"{company} {role} 官方校招页已出现27届/2027届信息",
                        jd_url=page.url or url,
                        channel=source.get("channel", "大厂巡检"),
                        tags=["27届", "巡检", company[:20]],
                        source_site=sid,
                        legitimacy="trusted",
                    )
                )
                logger.info("campus_patrol %s: hit 27届", sid)
            except Exception as e:
                logger.warning("campus_patrol %s failed: %s", sid, e)

        if own_fetcher:
            await fetcher.close()
        return jobs


def _guess_batch(text: str) -> str:
    for pat in (r"27届[^，。\n]{0,12}提前批", r"27届[^，。\n]{0,12}实习", r"2027届[^，。\n]{0,12}校招", r"27届实习"):
        m = re.search(pat, text)
        if m:
            return m.group(0).strip()
    return "27届校招"
