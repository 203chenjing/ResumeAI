"""官方 ATS JSON API Provider（S2）：Greenhouse / Ashby / Lever。

零 token、零 Playwright，直连公司招聘系统的官方公开 board JSON 接口，
字段干净（title/location/url/updated_at），合规且高时效。对标 career-ops scan.mjs。
"""
from __future__ import annotations

import logging
import uuid

import httpx

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.fetcher import CrawlFetcher
from app.services.job_validator import is_china_location

logger = logging.getLogger(__name__)

CAMPUS_HINT = ("intern", "campus", "new grad", "graduate", "校招", "实习", "应届")


def _greenhouse(company: dict, rows: list[dict]) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    name = company.get("name", company.get("board", ""))
    for j in rows:
        title = (j.get("title") or "").strip()
        url = j.get("absolute_url") or ""
        loc = ((j.get("location") or {}).get("name") or "").strip()
        jobs.append(
            JobPosting(
                id=f"gh_{j.get('id') or uuid.uuid4().hex[:8]}",
                company=name,
                role=title[:120],
                source="ats_board",
                jd_text=f"{name} {title} {loc}".strip(),
                jd_url=url,
                location=loc,
                channel="企业ATS",
                tags=["企业ATS", "Greenhouse"],
                published_at=(j.get("updated_at") or "")[:10],
                legitimacy="trusted",
            )
        )
    return jobs


def _lever(company: dict, rows: list[dict]) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    name = company.get("name", company.get("board", ""))
    for j in rows:
        title = (j.get("text") or "").strip()
        url = j.get("hostedUrl") or j.get("applyUrl") or ""
        cats = j.get("categories") or {}
        loc = (cats.get("location") or "").strip()
        jobs.append(
            JobPosting(
                id=f"lv_{j.get('id') or uuid.uuid4().hex[:8]}",
                company=name,
                role=title[:120],
                source="ats_board",
                jd_text=f"{name} {title} {loc}".strip(),
                jd_url=url,
                location=loc,
                channel="企业ATS",
                tags=["企业ATS", "Lever"],
                legitimacy="trusted",
            )
        )
    return jobs


def _ashby(company: dict, payload: dict) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    name = company.get("name", company.get("board", ""))
    rows = (payload.get("jobs") or payload.get("data") or {})
    if isinstance(rows, dict):
        rows = rows.get("jobPostings") or []
    for j in rows or []:
        title = (j.get("title") or "").strip()
        url = j.get("jobUrl") or j.get("applyUrl") or ""
        loc = (j.get("locationName") or j.get("location") or "").strip()
        jobs.append(
            JobPosting(
                id=f"ab_{j.get('id') or uuid.uuid4().hex[:8]}",
                company=name,
                role=title[:120],
                source="ats_board",
                jd_text=f"{name} {title} {loc}".strip(),
                jd_url=url,
                location=loc,
                channel="企业ATS",
                tags=["企业ATS", "Ashby"],
                legitimacy="trusted",
            )
        )
    return jobs


def _board_url(platform: str, board: str) -> str:
    if platform == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    if platform == "lever":
        return f"https://api.lever.co/v0/postings/{board}?mode=json"
    if platform == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{board}"
    return ""


def _campus_only(jobs: list[JobPosting]) -> list[JobPosting]:
    out = []
    for j in jobs:
        blob = f"{j.role}".lower()
        if any(h in blob for h in CAMPUS_HINT):
            out.append(j)
    return out


def _china_only(jobs: list[JobPosting]) -> list[JobPosting]:
    return [j for j in jobs if is_china_location(f"{j.location} {j.role}")]


class AtsBoardProvider(CrawlerProvider):
    name = "ats_board"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: CrawlFetcher | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        if not config.get("enabled", True):
            return []

        only_campus = bool(config.get("campus_only", True))
        only_china = bool(config.get("china_only", True))
        max_items = int(config.get("max_items_per_board", 60))
        ua = "ResumeAI-Crawler/1.0 (+ats board consumer)"
        jobs: list[JobPosting] = []

        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True, headers={"User-Agent": ua}
        ) as http:
            for company in config.get("sources") or []:
                if company.get("enabled") is False:
                    continue
                platform = (company.get("platform") or "").lower()
                board = company.get("board", "")
                url = _board_url(platform, board)
                if not url:
                    logger.warning("ats_board: unknown platform %s", platform)
                    continue
                try:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    if platform == "greenhouse":
                        items = _greenhouse(company, data.get("jobs") or [])
                    elif platform == "lever":
                        items = _lever(company, data if isinstance(data, list) else [])
                    else:
                        items = _ashby(company, data)
                    if only_campus:
                        items = _campus_only(items)
                    if only_china:
                        items = _china_only(items)
                    items = items[:max_items]
                    logger.info("ats_board %s/%s: %d jobs", platform, board, len(items))
                    jobs.extend(items)
                except Exception as e:
                    logger.warning("ats_board %s/%s failed: %s", platform, board, e)
        return jobs
