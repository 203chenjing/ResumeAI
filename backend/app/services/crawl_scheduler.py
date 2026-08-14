"""后台定时爬取：分 provider 错峰执行，避免单次 28 分钟全量超时。"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services.crawl_health import record_crawl_run
from app.services.job_digest import build_job_digest
from app.services.job_feed import crawl_all

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# (provider, hour, minute) — 27 届专项源优先，错峰执行
STAGGERED_PROVIDERS: list[tuple[str, int, int]] = [
    ("qiuzhao_system", 5, 30),
    ("browser_discovery", 5, 40),
    ("wechat_discovery", 5, 45),
    ("github_joblist", 5, 50),
    ("early_batch", 5, 55),
    ("job_aggregator", 6, 0),
    ("search_discovery", 6, 15),
    ("company_campus", 7, 0),
    ("campus_patrol", 7, 15),
    ("university_html", 7, 30),
]


async def _scheduled_crawl_provider(provider: str) -> None:
    client_id = settings.crawl_schedule_client_id
    try:
        result = await crawl_all(client_id, [provider])
        record_crawl_run(
            client_id,
            report=result.get("report") or [],
            new_count=result.get("new_count", 0),
            total=result.get("total", 0),
        )
        logger.info(
            "scheduled crawl %s done: +%s total=%s",
            provider,
            result.get("new_count"),
            result.get("total"),
        )
    except Exception:
        logger.exception("scheduled crawl %s failed", provider)


async def _scheduled_digest() -> None:
    client_id = settings.crawl_schedule_client_id
    try:
        await build_job_digest(client_id)
        logger.info("scheduled digest done for %s", client_id)
    except Exception:
        logger.exception("scheduled digest failed")


def start_crawl_scheduler() -> None:
    global _scheduler
    if not settings.crawl_schedule_enabled:
        return
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    for provider, hour, minute in STAGGERED_PROVIDERS:
        _scheduler.add_job(
            _scheduled_crawl_provider,
            "cron",
            hour=hour,
            minute=minute,
            args=[provider],
            id=f"crawl_{provider}",
            replace_existing=True,
        )
    digest_hour = settings.crawl_schedule_hour
    digest_minute = settings.crawl_schedule_minute
    _scheduler.add_job(
        _scheduled_digest,
        "cron",
        hour=digest_hour,
        minute=digest_minute,
        id="daily_digest",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "crawl scheduler started: providers %s, digest @ %02d:%02d client=%s",
        [p[0] for p in STAGGERED_PROVIDERS],
        digest_hour,
        digest_minute,
        settings.crawl_schedule_client_id,
    )


def stop_crawl_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
