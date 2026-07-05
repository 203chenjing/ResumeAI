"""浏览器模拟人操作：分步检索 27 届校招信息。

步骤：
  1. 生成检索词
  2. Playwright 打开搜索引擎结果页
  3. 筛选官方/可信链接
  4. 逐页访问（限速、等待渲染）
  5. DeepSeek 从页面正文提取结构化岗位
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.config import settings
from app.crawlers.base import JobPosting
from app.crawlers.crawl_config import get_compliance
from app.crawlers.fetcher import CrawlFetcher
from app.services.browser_search import browser_search_sync
from app.services.discovery_fallback import make_fallback_job_from_page
from app.services.llm_client import client

logger = logging.getLogger(__name__)

BLOCKED_HOSTS = (
    "zhipin.com",
    "liepin.com",
    "51job.com",
    "yingjiesheng.com",
    "zhihu.com/question",
    "baidu.com/link",
)

PREFERRED_HOST_HINTS = (
    "campus",
    "join.",
    "talent.",
    "careers.",
    "jobs.",
    "nowcoder.com/enterprise",
    "mp.weixin.qq.com",
)

DEFAULT_QUERIES = (
    "2027届校招 提前批 官方投递",
    "27届秋招 互联网 校园招聘 2026",
    "2027届 暑期实习 大厂 官网",
    "27届 校招 字节 腾讯 美团 官方",
)

EXTRACT_SYSTEM = """你是校招页面阅读助手。用户给你从官网/招聘页抓取的正文，请提取面向 27届/2027届 的可投递机会。
输出 JSON（无 markdown）：
{
  "jobs": [
    {
      "company": "公司",
      "role": "岗位或批次名（含27届/实习/提前批等）",
      "jd_url": "本页或页面中的官方投递链接",
      "jd_text": "≤80字摘要",
      "job_type": "提前批|秋招|春招|实习|校招",
      "graduation_cohort": "27届"
    }
  ]
}
规则：
- 优先提取 27届/2027届；若无届别但页面是官方 campus/校招页，也保留 1 条汇总入口
- 只提取真实招聘/投递入口；可从页面标题推断公司名
- jobs 为空时用户会降级入库，尽量至少给出 1 条可投递线索"""


@dataclass
class StepReport:
    step: int
    name: str
    status: str
    detail: str = ""
    count: int = 0

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "count": self.count,
        }


@dataclass
class PipelineState:
    reports: list[StepReport] = field(default_factory=list)
    jobs: list[JobPosting] = field(default_factory=list)


def build_queries(config: dict) -> list[str]:
    custom = [str(q).strip() for q in (config.get("queries") or []) if str(q).strip()]
    cohort = config.get("target_cohort") or "27届"
    base = custom or list(DEFAULT_QUERIES)
    if cohort and cohort not in "".join(base):
        base = [f"{cohort} {q}" for q in base[:2]] + base
    max_q = int(config.get("max_queries", 4))
    return base[:max_q]


def _browser_search_sync(query: str, user_agent: str, max_results: int, timeout: float) -> list[dict]:
    return browser_search_sync(query, user_agent, max_results, timeout)


def filter_official_urls(results: list[dict], *, max_urls: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in results:
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        if not url.startswith("http"):
            continue
        host = urlparse(url).netloc.lower()
        if any(b in host or b in url for b in BLOCKED_HOSTS):
            continue
        if url in seen:
            continue
        seen.add(url)
        score = 0
        if any(h in url.lower() or h in host for h in PREFERRED_HOST_HINTS):
            score += 2
        if re.search(r"27届|2027届|校招|campus|提前批", f"{title} {url}", re.I):
            score += 2
        out.append({**row, "_score": score})
    out.sort(key=lambda x: -x.get("_score", 0))
    return out[:max_urls]


async def _extract_jobs_from_page(company_hint: str, url: str, text: str, cohort: str) -> list[dict]:
    if not settings.deepseek_api_key:
        return []
    snippet = (text or "")[:4500]
    if len(snippet) < 80:
        return []
    user = json.dumps(
        {"target_cohort": cohort, "page_url": url, "company_hint": company_hint, "page_text": snippet},
        ensure_ascii=False,
    )
    try:
        data = await client.chat_json(EXTRACT_SYSTEM, user, max_tokens=2500, temperature=0.1)
        return list(data.get("jobs") or [])
    except Exception:
        logger.exception("browser_discovery extract failed url=%s", url[:80])
        return []


async def run_browser_discovery_pipeline(config: dict | None = None) -> tuple[list[JobPosting], list[dict]]:
    config = config or {}
    if not config.get("enabled", True):
        return [], [StepReport(0, "跳过", "skipped", "browser_discovery disabled").to_dict()]

    compliance = get_compliance()
    user_agent = compliance.get("user_agent", "ResumeAI-BrowserDiscovery/1.0")
    cohort = config.get("target_cohort") or "27届"
    max_results = int(config.get("max_search_results_per_query", 8))
    max_pages = int(config.get("max_pages_to_visit", 12))
    visit_wait_ms = int(config.get("visit_wait_ms", 3500))
    timeout = float(config.get("timeout", 75))
    channel = config.get("channel", "浏览器检索")

    reports: list[dict] = []
    fetcher = CrawlFetcher(compliance)

    queries = build_queries(config)
    reports.append(StepReport(1, "生成检索词", "ok", "、".join(queries[:3]), len(queries)).to_dict())

    search_hits: list[dict] = []
    try:
        for q in queries:
            hits = _browser_search_sync(q, user_agent, max_results, timeout)
            for h in hits:
                h["query"] = q
            search_hits.extend(hits)
        status = "ok" if search_hits else "warn"
        detail = f"{len(queries)} 组关键词" if search_hits else "搜索无结果，跳过"
        reports.append(StepReport(2, "浏览器搜索", status, detail, len(search_hits)).to_dict())
    except Exception as e:
        logger.exception("browser search failed")
        reports.append(StepReport(2, "浏览器搜索", "warn", str(e)[:120], 0).to_dict())

    candidates = filter_official_urls(search_hits, max_urls=max_pages)
    reports.append(StepReport(3, "筛选官方链接", "ok", f"保留 {len(candidates)} 条", len(candidates)).to_dict())

    raw_jobs: list[JobPosting] = []
    visited = 0
    for cand in candidates:
        url = cand.get("url") or ""
        title = cand.get("title") or ""
        try:
            page = await fetcher.fetch(
                url,
                use_playwright=True,
                ignore_robots=True,
                wait_ms=visit_wait_ms,
                timeout=timeout,
                wait_until="domcontentloaded",
            )
            visited += 1
            extracted = await _extract_jobs_from_page(title, page.url or url, page.text, cohort)
            added = False
            for row in extracted:
                company = str(row.get("company") or title or "待确认公司").strip()[:60]
                role = str(row.get("role") or "27届校招").strip()[:120]
                jd_url = str(row.get("jd_url") or page.url or url).strip()
                if not jd_url.startswith("http"):
                    continue
                raw_jobs.append(
                    JobPosting(
                        id=uuid.uuid4().hex[:12],
                        company=company,
                        role=role,
                        source="browser_discovery",
                        jd_text=str(row.get("jd_text") or f"{company} {role}")[:500],
                        jd_url=jd_url,
                        channel=channel,
                        tags=[cohort, "浏览器检索", str(row.get("job_type") or "校招")],
                        job_type=str(row.get("job_type") or "校招")[:20],
                        legitimacy="likely",
                    )
                )
                added = True
            if not added:
                page_url = page.url or url
                fallback = make_fallback_job_from_page(
                    title=title,
                    url=page_url,
                    text=(page.text or "") + " " + title,
                    cohort=cohort,
                    source="browser_discovery",
                    channel=channel,
                    extra_tags=["浏览器检索"],
                )
                if not fallback and (
                    any(h in page_url.lower() for h in PREFERRED_HOST_HINTS)
                    or re.search(r"27届|2027|校招|campus", f"{title} {page_url}", re.I)
                ):
                    from app.services.discovery_fallback import guess_company

                    fallback = JobPosting(
                        id=uuid.uuid4().hex[:12],
                        company=guess_company(title)[:60],
                        role=(title or f"{cohort}校招")[:120],
                        source="browser_discovery",
                        jd_text=(title + " " + (page.text or "")[:400])[:500],
                        jd_url=page_url,
                        channel=channel,
                        tags=[cohort, "浏览器检索", "降级入库", "待审核"],
                        job_type="校招",
                        legitimacy="likely",
                    )
                if fallback:
                    raw_jobs.append(fallback)
        except Exception as e:
            logger.warning("browser visit failed %s: %s", url[:80], e)

    await fetcher.close()

    reports.append(StepReport(4, "逐页访问", "ok", f"打开 {visited} 页", visited).to_dict())
    reports.append(StepReport(5, "AI 提取岗位", "ok", "结构化解析", len(raw_jobs)).to_dict())

    return raw_jobs, reports
