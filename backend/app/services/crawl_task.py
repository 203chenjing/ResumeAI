"""后台爬虫任务：与改稿并行，不阻塞 HTTP 长连接。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

STUDIO_PATH_PREFIXES = (
    "/api/parse-resume",
    "/api/analyze-jd",
    "/api/analyze-match",
    "/api/generate-suggestions",
    "/api/build-resume-from-knowledge",
    "/api/chat",
    "/api/chat/agent",
    "/api/agent/run",
    "/api/export-pdf",
    "/api/finalize",
)


@dataclass
class CrawlTaskState:
    status: str = "idle"  # idle | running | done | error
    client_id: str = ""
    providers: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    progress: str = ""
    result: dict[str, Any] | None = None
    error: str = ""

    def to_api(self) -> dict[str, Any]:
        base = {
            "status": self.status,
            "client_id": self.client_id,
            "providers": self.providers,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": self.progress,
        }
        if self.status == "done" and self.result:
            base.update(self.result)
        if self.status == "error":
            base["error"] = self.error
        return base


_lock = asyncio.Lock()
_task: asyncio.Task | None = None
_state = CrawlTaskState()


async def get_crawl_state() -> CrawlTaskState:
    async with _lock:
        return _state


async def start_crawl(client_id: str, providers: list[str] | None) -> CrawlTaskState:
    global _task, _state
    async with _lock:
        if _state.status == "running" and _task and not _task.done():
            return _state

        _state = CrawlTaskState(
            status="running",
            client_id=client_id,
            providers=list(providers or []),
            started_at=datetime.now().isoformat(timespec="seconds"),
            progress="正在抓取岗位…",
        )
        _task = asyncio.create_task(_run_crawl(client_id, providers))
        return _state


async def _run_crawl(client_id: str, providers: list[str] | None) -> None:
    global _state
    try:
        from app.services.crawl_health import record_crawl_run
        from app.services.job_digest import build_job_digest
        from app.services.job_feed import crawl_all, list_jobs

        _state.progress = "正在抓取岗位源…"
        result = await crawl_all(client_id, providers)

        _state.progress = "正在生成岗位摘要…"
        health = record_crawl_run(
            client_id,
            report=result.get("report") or [],
            new_count=result.get("new_count", 0),
            total=result.get("total", 0),
        )
        new_ids = [j.get("id") for j in result.get("new_jobs") or [] if j.get("id")]
        digest = await build_job_digest(client_id, new_job_ids=new_ids)

        _state.status = "done"
        _state.result = {
            "new_count": result["new_count"],
            "total": result["total"],
            "report": result["report"],
            "quality": result.get("quality"),
            "jobs": list_jobs(client_id),
            "digest": digest,
            "crawl_health": health,
        }
        _state.progress = "抓取完成"
        logger.info(
            "background crawl done client=%s new=%s total=%s",
            client_id,
            result.get("new_count"),
            result.get("total"),
        )
    except Exception as e:
        logger.exception("background crawl failed")
        _state.status = "error"
        _state.error = str(e)
        _state.progress = "抓取失败"
    finally:
        _state.finished_at = datetime.now().isoformat(timespec="seconds")
