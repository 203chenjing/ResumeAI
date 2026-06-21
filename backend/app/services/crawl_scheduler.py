"""后台定时爬取（可选开启）。"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services.crawl_health import record_crawl_run
from app.services.job_digest import build_job_digest
from app.services.job_feed import crawl_all

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _scheduled_crawl() -> None:
    client_id = settings.crawl_schedule_client_id
    try:
        result = await crawl_all(client_id, None)
        record_crawl_run(
            client_id,
            report=result.get("report") or [],
            new_count=result.get("new_count", 0),
            total=result.get("total", 0),
        )
        new_ids = [j.get("id") for j in result.get("new_jobs") or [] if j.get("id")]
        await build_job_digest(client_id, new_job_ids=new_ids)
        logger.info("scheduled crawl done: +%s total=%s", result.get("new_count"), result.get("total"))
    except Exception:
        logger.exception("scheduled crawl failed")


def start_crawl_scheduler() -> None:
    global _scheduler
    if not settings.crawl_schedule_enabled:
        return
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _scheduled_crawl,
        "cron",
        hour=settings.crawl_schedule_hour,
        minute=settings.crawl_schedule_minute,
        id="daily_crawl",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "crawl scheduler started @ %02d:%02d client=%s",
        settings.crawl_schedule_hour,
        settings.crawl_schedule_minute,
        settings.crawl_schedule_client_id,
    )


def stop_crawl_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
