"""公众号专项：搜狗微信搜索 + 浏览器检索 → 发现文章 → 结构化阅读 → AI 提取校招信息。

步骤（借鉴 WechatSogou / wechat-download-api 高星项目）：
  1. 生成检索词（搜狗直搜 + Bing site:mp.weixin.qq.com）
  2a. 搜狗微信 type=2 文章搜索，解析跳转链为 mp.weixin URL
  2b. 浏览器搜索引擎补充发现
  3. 从牛客等汇总页 harvest 更多 mp.weixin 链接
  4. 去重筛选有效文章 URL
  5. httpx 移动端 UA 抓取 #js_content（Playwright 兜底）
  6. DeepSeek 从正文 + 投递链接提取结构化岗位
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid

from app.config import settings
from app.crawlers.base import JobPosting
from app.crawlers.crawl_config import get_compliance
from app.crawlers.fetcher import CrawlFetcher
from app.services.browser_search import browser_search_sync
from app.crawlers.wechat_article import extract_wechat_urls
from app.services.browser_discovery import StepReport
from app.services.llm_client import client
from app.services.wechat_article_parser import parse_wechat_article_html
from app.services.wechat_fetch import fetch_wechat_article
from app.services.wechat_sogou import search_wechat_articles

logger = logging.getLogger(__name__)

MP_WECHAT_PATH_RE = re.compile(r"mp\.weixin\.qq\.com/s(?:/[A-Za-z0-9_\-]+|\?)", re.I)

DEFAULT_WECHAT_QUERIES = (
    "site:mp.weixin.qq.com 2027届校招",
    "site:mp.weixin.qq.com 27届 提前批",
    "site:mp.weixin.qq.com 27届 暑期实习 大厂",
    "校招汇 公众号 27届 2027",
    "牛客 公众号 27届 校招 投递",
)

DEFAULT_SOGOU_QUERIES = (
    "2027届校招",
    "27届 提前批",
    "27届 暑期实习 大厂",
    "27届 秋招 启动",
    "校招汇 27届",
)

_SITE_PREFIX_RE = re.compile(r"site:mp\.weixin\.qq\.com\s*", re.I)

WECHAT_EXTRACT_SYSTEM = """你是校招公众号文章阅读助手。用户给你从 mp.weixin.qq.com 抓取的正文，请提取面向 27届/2027届 的可投递机会。
输出 JSON（无 markdown）：
{
  "jobs": [
    {
      "company": "公司全称或简称",
      "role": "岗位/批次名（含27届/实习/提前批/秋招等）",
      "jd_url": "官方投递链接（文章内链接优先，否则用文章 URL）",
      "jd_text": "≤100字摘要（含截止日、城市、要求要点）",
      "job_type": "提前批|秋招|春招|实习|校招|补录",
      "graduation_cohort": "27届",
      "deadline": "YYYY-MM-DD 或空"
    }
  ]
}
规则：
- 一篇文可能含多家公司/多条批次，尽量拆成多条 jobs
- 只保留真实招聘/投递信息；纯经验贴、无投递入口则 jobs 为空数组
- 文章里的官网/campus/内推链接写入 jd_url；apply_links_in_article 优先；没有则用文章 URL"""


def build_wechat_queries(config: dict) -> list[str]:
    custom = [str(q).strip() for q in (config.get("queries") or []) if str(q).strip()]
    cohort = config.get("target_cohort") or "27届"
    base = custom or list(DEFAULT_WECHAT_QUERIES)
    if cohort and cohort not in "".join(base):
        base = [f"site:mp.weixin.qq.com {cohort} 校招"] + base
    max_q = int(config.get("max_queries", 5))
    return base[:max_q]


def build_sogou_queries(config: dict) -> list[str]:
    """搜狗微信搜索词（去掉 site: 前缀，并追加订阅公众号名）。"""
    custom = [str(q).strip() for q in (config.get("sogou_queries") or config.get("queries") or []) if str(q).strip()]
    cohort = config.get("target_cohort") or "27届"
    base = [_SITE_PREFIX_RE.sub("", q).strip() for q in (custom or list(DEFAULT_SOGOU_QUERIES))]
    base = [q for q in base if q]
    accounts = [str(a).strip() for a in (config.get("subscribed_accounts") or []) if str(a).strip()]
    for acc in accounts:
        base.append(f"{acc} {cohort} 校招")
    if cohort and cohort not in "".join(base):
        base.insert(0, f"{cohort} 校招")
    max_q = int(config.get("max_sogou_queries", config.get("max_queries", 6)))
    seen: set[str] = set()
    deduped: list[str] = []
    for q in base:
        if q not in seen:
            seen.add(q)
            deduped.append(q)
    return deduped[:max_q]


def _browser_search_sync(query: str, user_agent: str, max_results: int, timeout: float) -> list[dict]:
    return browser_search_sync(query, user_agent, max_results, timeout)


def _canonical_wechat_url(url: str) -> str | None:
    url = (url or "").strip()
    if not MP_WECHAT_PATH_RE.search(url):
        return None
    if not url.startswith("http"):
        return None
    base = url.split("#")[0]
    if "/s/" in base:
        return base.split("?")[0]
    return base


def filter_wechat_article_urls(results: list[dict], *, max_urls: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in results:
        url = _canonical_wechat_url(row.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        title = (row.get("title") or "").strip()
        score = 0
        if re.search(r"27届|2027届|校招|提前批|实习|秋招", f"{title} {url}", re.I):
            score += 3
        if row.get("from") == "discovery":
            score += 1
        if row.get("from") == "sogou":
            score += 2
        out.append({**row, "url": url, "_score": score})
    out.sort(key=lambda x: -x.get("_score", 0))
    return out[:max_urls]


async def _harvest_from_discovery_pages(
    fetcher: CrawlFetcher,
    sources: list,
    *,
    timeout: float,
    wait_ms: int,
) -> list[dict]:
    hits: list[dict] = []
    for disc in sources:
        if isinstance(disc, str):
            disc = {"url": disc}
        page_url = (disc.get("url") or "").strip()
        if not page_url:
            continue
        try:
            page = await fetcher.fetch(
                page_url,
                use_playwright=bool(disc.get("use_playwright", True)),
                ignore_robots=bool(disc.get("ignore_robots", False)),
                wait_ms=int(disc.get("wait_ms", wait_ms)),
                timeout=timeout,
            )
            for wu in extract_wechat_urls(page.html):
                canon = _canonical_wechat_url(wu)
                if canon:
                    hits.append({"title": disc.get("name") or "汇总页", "url": canon, "from": "discovery"})
        except Exception as e:
            logger.warning("wechat harvest failed %s: %s", page_url[:80], e)
    return hits


async def _extract_jobs_from_wechat(
    title: str,
    url: str,
    text: str,
    cohort: str,
    *,
    apply_links: list[str] | None = None,
    account_name: str = "",
) -> list[dict]:
    if not settings.deepseek_api_key:
        return []
    snippet = (text or "")[:6000]
    if len(snippet) < 60:
        return []
    user = json.dumps(
        {
            "target_cohort": cohort,
            "article_url": url,
            "article_title": title,
            "account_name": account_name,
            "apply_links_in_article": apply_links or [],
            "article_text": snippet,
        },
        ensure_ascii=False,
    )
    try:
        data = await client.chat_json(WECHAT_EXTRACT_SYSTEM, user, max_tokens=3000, temperature=0.1)
        return list(data.get("jobs") or [])
    except Exception:
        logger.exception("wechat_discovery extract failed url=%s", url[:80])
        return []


async def _sogou_search_articles(query: str, max_results: int, timeout: float) -> list[dict]:
    return await asyncio.to_thread(search_wechat_articles, query, max_results=max_results, timeout=timeout)


async def _read_wechat_article(
    fetcher: CrawlFetcher,
    url: str,
    *,
    timeout: float,
    visit_wait_ms: int,
    fallback_playwright: bool,
):
    article = await fetch_wechat_article(url, timeout=min(timeout, 30.0))
    if len(article.content_text) >= 60 or not fallback_playwright:
        return article
    try:
        page = await fetcher.fetch(
            url,
            use_playwright=True,
            ignore_robots=True,
            wait_ms=visit_wait_ms,
            timeout=timeout,
            wait_until="domcontentloaded",
        )
        parsed = parse_wechat_article_html(page.html or "", page.url or url)
        if len(parsed.content_text) > len(article.content_text):
            return parsed
    except Exception as e:
        logger.debug("wechat playwright fallback failed %s: %s", url[:60], e)
    return article


async def run_wechat_discovery_pipeline(config: dict | None = None) -> tuple[list[JobPosting], list[dict]]:
    config = config or {}
    if not config.get("enabled", True):
        return [], [StepReport(0, "跳过", "skipped", "wechat_discovery disabled").to_dict()]

    compliance = get_compliance()
    user_agent = compliance.get("user_agent", "ResumeAI-WechatDiscovery/1.0")
    cohort = config.get("target_cohort") or "27届"
    max_results = int(config.get("max_search_results_per_query", 10))
    max_articles = int(config.get("max_articles_to_visit", 15))
    visit_wait_ms = int(config.get("visit_wait_ms", 5000))
    timeout = float(config.get("timeout", 90))
    channel = config.get("channel", "公众号")
    use_sogou = config.get("use_sogou", True)
    use_bing = config.get("use_bing_search", True)
    fallback_playwright = config.get("fallback_playwright", True)
    sogou_timeout = float(config.get("sogou_timeout", 22))

    reports: list[dict] = []
    fetcher = CrawlFetcher(compliance)

    sogou_queries = build_sogou_queries(config) if use_sogou else []
    bing_queries = build_wechat_queries(config) if use_bing else []
    reports.append(
        StepReport(
            1,
            "生成公众号检索词",
            "ok",
            f"搜狗 {len(sogou_queries)} + Bing {len(bing_queries)}",
            len(sogou_queries) + len(bing_queries),
        ).to_dict()
    )

    sogou_hits: list[dict] = []
    if use_sogou and sogou_queries:
        try:
            for q in sogou_queries:
                hits = await _sogou_search_articles(q, max_results, sogou_timeout)
                for h in hits:
                    h["query"] = q
                    h["from"] = "sogou"
                    canon = _canonical_wechat_url(h.get("url") or "")
                    if canon:
                        sogou_hits.append({**h, "url": canon})
                await asyncio.sleep(0.8)
            status = "ok" if sogou_hits else "warn"
            detail = f"{len(sogou_queries)} 组搜狗词" if sogou_hits else "搜狗无结果或验证码"
            reports.append(StepReport(2, "搜狗微信搜索", status, detail, len(sogou_hits)).to_dict())
        except Exception as e:
            logger.exception("wechat sogou search failed")
            reports.append(StepReport(2, "搜狗微信搜索", "warn", str(e)[:120], 0).to_dict())

    search_hits: list[dict] = list(sogou_hits)
    if use_bing and bing_queries:
        try:
            for q in bing_queries:
                hits = _browser_search_sync(q, user_agent, max_results, timeout)
                for h in hits:
                    h["query"] = q
                    h["from"] = h.get("from") or "bing"
                    canon = _canonical_wechat_url(h.get("url") or "")
                    if canon:
                        search_hits.append({**h, "url": canon})
            bing_only = len(search_hits) - len(sogou_hits)
            status = "ok" if bing_only else "warn"
            detail = f"{len(bing_queries)} 组 Bing 词" if bing_only else "Bing 无补充结果"
            reports.append(StepReport(3, "浏览器搜索补充", status, detail, bing_only).to_dict())
        except Exception as e:
            logger.exception("wechat browser search failed")
            reports.append(StepReport(3, "浏览器搜索补充", "warn", str(e)[:120], 0).to_dict())

    discovery_sources = config.get("discovery_sources") or []
    harvested = await _harvest_from_discovery_pages(
        fetcher,
        discovery_sources,
        timeout=timeout,
        wait_ms=visit_wait_ms,
    )
    reports.append(
        StepReport(4, "汇总页 harvest 链接", "ok", f"{len(discovery_sources)} 个来源", len(harvested)).to_dict()
    )

    candidates = filter_wechat_article_urls(search_hits + harvested, max_urls=max_articles)
    reports.append(StepReport(5, "筛选文章链接", "ok", f"保留 {len(candidates)} 篇", len(candidates)).to_dict())

    raw_jobs: list[JobPosting] = []
    visited = 0
    for cand in candidates:
        url = cand.get("url") or ""
        title = (cand.get("title") or "公众号校招").strip()
        try:
            article = await _read_wechat_article(
                fetcher,
                url,
                timeout=timeout,
                visit_wait_ms=visit_wait_ms,
                fallback_playwright=fallback_playwright,
            )
            visited += 1
            page_title = article.title or title
            page_url = article.url or url
            body = article.content_text

            extracted = await _extract_jobs_from_wechat(
                page_title,
                page_url,
                body,
                cohort,
                apply_links=article.apply_links,
                account_name=article.account_name,
            )
            if not extracted:
                company = _guess_company(page_title + " " + (body or "")[:500])
                jd_url = article.apply_links[0] if article.apply_links else page_url
                raw_jobs.append(
                    JobPosting(
                        id=uuid.uuid4().hex[:12],
                        company=company,
                        role=page_title[:100],
                        source="wechat_discovery",
                        jd_text=(body or page_title)[:800],
                        jd_url=jd_url,
                        channel=channel,
                        tags=[cohort, "公众号", "搜狗/浏览器挖掘"],
                        job_type="校招",
                        legitimacy="likely",
                    )
                )
                continue

            for row in extracted:
                company = str(row.get("company") or article.account_name or page_title or "待确认公司").strip()[:60]
                role = str(row.get("role") or page_title).strip()[:120]
                jd_url = str(row.get("jd_url") or "").strip()
                if not jd_url.startswith("http"):
                    jd_url = (article.apply_links[0] if article.apply_links else page_url)
                tags = [cohort, "公众号", str(row.get("job_type") or "校招")]
                deadline = str(row.get("deadline") or "").strip()
                if deadline:
                    tags.append(f"截止:{deadline[:10]}")
                raw_jobs.append(
                    JobPosting(
                        id=uuid.uuid4().hex[:12],
                        company=company,
                        role=role,
                        source="wechat_discovery",
                        jd_text=str(row.get("jd_text") or f"{company} {role}")[:800],
                        jd_url=jd_url,
                        channel=channel,
                        tags=tags,
                        job_type=str(row.get("job_type") or "校招")[:20],
                        legitimacy="likely",
                    )
                )
        except Exception as e:
            logger.warning("wechat article visit failed %s: %s", url[:80], e)

    await fetcher.close()

    reports.append(StepReport(6, "逐篇阅读", "ok", f"打开 {visited} 篇", visited).to_dict())
    reports.append(StepReport(7, "AI 提取岗位", "ok", "结构化解析", len(raw_jobs)).to_dict())

    return raw_jobs, reports


def _guess_company(text: str) -> str:
    for kw in ("字节跳动", "字节", "阿里巴巴", "阿里", "腾讯", "华为", "美团", "京东", "百度", "小米", "网易", "快手"):
        if kw in text:
            return "字节跳动" if kw == "字节" else ("阿里巴巴" if kw == "阿里" else kw)
    m = re.search(r"([\u4e00-\u9fff]{2,20}(?:有限公司|集团|银行))", text)
    return m.group(1) if m else "待确认公司"
