"""公众号文章 URL ingest（L4）：支持 crawl_sources.yml 持久订阅列表。"""
from __future__ import annotations

import logging
import re
import uuid

import httpx

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.fetcher import CrawlFetcher

logger = logging.getLogger(__name__)


MP_WECHAT_RE = re.compile(r"https?://mp\.weixin\.qq\.com/s/[A-Za-z0-9_\-?=&%]+", re.I)


def extract_wechat_urls(html: str) -> list[str]:
    found = MP_WECHAT_RE.findall(html)
    # 去掉 query 保持 canonical
    out: list[str] = []
    seen: set[str] = set()
    for u in found:
        base = u.split("?")[0]
        if base not in seen:
            seen.add(base)
            out.append(u if "?" in u else u)
    return out


class WechatArticleProvider(CrawlerProvider):
    name = "wechat_article"

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

        urls: list[str] = list(config.get("subscribed_urls") or [])
        for u in config.get("urls") or []:
            if isinstance(u, str):
                urls.append(u)
            elif isinstance(u, dict) and u.get("url"):
                urls.append(u["url"])

        # 从公开汇总页发现公众号文章链接（仅 mp.weixin.qq.com 公开文章）
        for disc in config.get("discovery_sources") or []:
            if isinstance(disc, str):
                disc = {"url": disc}
            page_url = disc.get("url", "")
            if not page_url:
                continue
            try:
                use_pw = disc.get("use_playwright", True)
                page = await fetcher.fetch(
                    page_url,
                    use_playwright=use_pw,
                    ignore_robots=bool(disc.get("ignore_robots", False)),
                    wait_ms=int(disc.get("wait_ms", 2000)),
                )
                for wu in extract_wechat_urls(page.html):
                    urls.append(wu)
                logger.info("wechat discovery %s: found %d urls", disc.get("name", page_url), len(extract_wechat_urls(page.html)))
            except Exception as e:
                logger.warning("wechat discovery failed %s: %s", page_url, e)

        # 去重
        deduped: list[str] = []
        seen_u: set[str] = set()
        for u in urls:
            key = u.split("?")[0]
            if key not in seen_u:
                seen_u.add(key)
                deduped.append(u)

        jobs: list[JobPosting] = []
        for url in deduped[:30]:
            job = await self.ingest_url(url, fetcher=fetcher)
            if job:
                jobs.append(job)

        if own_fetcher:
            await fetcher.close()
        return jobs

    async def ingest_url(self, url: str, fetcher: CrawlFetcher | None = None) -> JobPosting | None:
        if not url.strip():
            return None

        title = "公众号校招资讯"
        description = ""
        final_url = url

        try:
            if fetcher:
                page = await fetcher.fetch_http(url)
                html = page.html
                final_url = page.url
            else:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http:
                    resp = await http.get(url, headers={"User-Agent": "ResumeAI-Crawler/1.0"})
                    html = resp.text
                    final_url = str(resp.url)

            t = re.search(
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                html,
                re.I,
            )
            d = re.search(
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
                html,
                re.I,
            )
            if t:
                title = t.group(1).strip()
            elif re.search(r"<title>([^<]+)</title>", html, re.I):
                title = re.search(r"<title>([^<]+)</title>", html, re.I).group(1).strip()
            if d:
                description = d.group(1).strip()
            if not description:
                description = re.sub(r"<[^>]+>", " ", html)
                description = re.sub(r"\s+", " ", description).strip()[:1200]
        except Exception as e:
            logger.warning("wechat ingest failed %s: %s", url, e)
            description = f"用户订阅文章：{url}"

        company = _guess_company(title + " " + description)
        return JobPosting(
            id=uuid.uuid4().hex[:12],
            company=company,
            role=title[:100],
            source=self.name,
            jd_text=description or title,
            jd_url=final_url,
            channel="公众号",
            tags=["待审核", "L4", "wechat"],
        )


def _guess_company(text: str) -> str:
    for kw in ("字节跳动", "字节", "阿里巴巴", "阿里", "腾讯", "华为", "美团", "京东", "百度", "小米", "网易", "快手"):
        if kw in text:
            return "字节跳动" if kw == "字节" else ("阿里巴巴" if kw == "阿里" else kw)
    m = re.search(r"([\u4e00-\u9fff]{2,20}(?:有限公司|集团|银行))", text)
    return m.group(1) if m else "待确认公司"
