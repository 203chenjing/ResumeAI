"""AI 提取为空时的降级入库（浏览器/搜索发现共用）。"""
from __future__ import annotations

import re
import uuid

from app.crawlers.base import JobPosting

CAMPUS_URL_HINTS = (
    "campus",
    "jobs.",
    "join.",
    "talent.",
    "careers.",
    "zhaopin.",
    "recruit",
    "campus-recruitment",
    "zhiye.com/campus",
    "mokahr.com/campus",
)

CAMPUS_TEXT_RE = re.compile(
    r"27届|2027届|2027\s*届|校招|校园招聘|提前批|暑期实习|实习招聘|graduate|campus",
    re.I,
)

BLOCKED_URL_PARTS = ("zhipin.com", "liepin.com", "51job.com", "yingjiesheng.com", "zhihu.com/question")


def looks_like_campus_url(url: str) -> bool:
    u = (url or "").lower()
    return bool(u.startswith("http")) and any(h in u for h in CAMPUS_URL_HINTS)


def looks_like_campus_text(text: str) -> bool:
    return bool(CAMPUS_TEXT_RE.search(text or ""))


def is_blocked_url(url: str) -> bool:
    u = (url or "").lower()
    return any(b in u for b in BLOCKED_URL_PARTS)


def guess_company(text: str) -> str:
    for kw in ("字节跳动", "字节", "阿里巴巴", "阿里", "腾讯", "华为", "美团", "京东", "百度", "小米", "网易", "快手", "滴滴"):
        if kw in text:
            return "字节跳动" if kw == "字节" else ("阿里巴巴" if kw == "阿里" else kw)
    m = re.search(r"([\u4e00-\u9fff]{2,20}(?:有限公司|集团|银行|科技))", text)
    return m.group(1) if m else "待确认公司"


def make_fallback_job_from_page(
    *,
    title: str,
    url: str,
    text: str,
    cohort: str,
    source: str,
    channel: str,
    extra_tags: list[str] | None = None,
) -> JobPosting | None:
    """页面像校招页但 AI 未抽出结构化岗位时，降级为 weak 可审核条目。"""
    url = (url or "").strip()
    if not url.startswith("http") or is_blocked_url(url):
        return None
    blob = f"{title} {(text or '')[:800]}"
    if not looks_like_campus_url(url) and not looks_like_campus_text(blob):
        return None
    company = guess_company(blob)
    role = (title or "").strip()[:120] or f"{cohort}校招"
    if len(role) < 4:
        role = f"{company} {cohort}校招"
    tags = [cohort, "降级入库", *(extra_tags or []), "待审核"]
    return JobPosting(
        id=uuid.uuid4().hex[:12],
        company=company[:60],
        role=role,
        source=source,
        jd_text=blob[:800],
        jd_url=url,
        channel=channel,
        tags=tags,
        job_type="校招",
        legitimacy="likely",
    )


def make_fallback_jobs_from_search_hits(
    hits: list[dict],
    *,
    cohort: str,
    source: str,
    channel: str,
    max_jobs: int = 15,
) -> list[JobPosting]:
    """搜索摘要直接降级为岗位线索（LLM 无输出时）。"""
    out: list[JobPosting] = []
    seen: set[str] = set()
    for hit in hits:
        url = (hit.get("url") or "").strip()
        title = (hit.get("title") or "").strip()
        snippet = (hit.get("snippet") or "").strip()
        if not url.startswith("http") or is_blocked_url(url):
            continue
        blob = f"{title} {snippet}"
        if not looks_like_campus_url(url) and not looks_like_campus_text(blob):
            continue
        key = url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        company = guess_company(blob)
        role = title[:120] if title else f"{company} {cohort}校招"
        out.append(
            JobPosting(
                id=uuid.uuid4().hex[:12],
                company=company[:60],
                role=role,
                source=source,
                jd_text=(snippet or title or company)[:500],
                jd_url=url,
                channel=channel,
                tags=[cohort, "搜索降级", "待审核"],
                job_type="校招",
                legitimacy="likely",
            )
        )
        if len(out) >= max_jobs:
            break
    return out
