"""后台爬虫任务：与改稿并行，不阻塞 HTTP 长连接。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

PROVIDER_LABELS: dict[str, str] = {
    "browser_discovery": "浏览器检索",
    "wechat_discovery": "公众号",
    "github_joblist": "GitHub 校招库",
    "early_batch": "27届提前批",
    "job_aggregator": "求职平台",
    "search_discovery": "AI 搜索",
    "company_campus": "企业官网",
    "campus_patrol": "大厂巡检",
    "university_html": "高校就业网",
    "wechat_article": "公众号",
    "ats_board": "ATS 招聘板",
}

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
    partial: dict[str, Any] = field(default_factory=dict)
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
        if self.status == "running" and self.partial:
            base.update(self.partial)
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
        from app.services.job_feed import all_enabled_providers, crawl_all, cross_verify_feed, list_jobs, organize_feed

        names = list(providers) if providers else all_enabled_providers()
        _state.providers = names
        total_steps = len(names) + 2  # +整理 +摘要

        async def on_progress(payload: dict) -> None:
            idx = payload.get("provider_index", 0)
            label = PROVIDER_LABELS.get(payload.get("provider", ""), payload.get("provider", "岗位源"))
            _state.progress = f"正在更新 ({idx}/{len(names)})：{label}"
            _state.partial = {
                "total": payload.get("total", 0),
                "new_count": payload.get("new_count", 0),
                "provider_index": idx,
                "provider_total": len(names),
                "current_provider": payload.get("provider"),
                "report": payload.get("report"),
            }

        _state.progress = "正在更新岗位库…"
        _state.partial = {"provider_index": 0, "provider_total": len(names), "total": 0, "new_count": 0}

        result = await crawl_all(
            client_id,
            names,
            incremental_save=True,
            on_progress=on_progress,
        )

        _state.progress = f"正在整理 ({len(names) + 1}/{total_steps})…"
        cross_stats = cross_verify_feed(client_id)
        organize_stats = await organize_feed(client_id)

        _state.progress = f"正在生成摘要 ({total_steps}/{total_steps})…"
        health = record_crawl_run(
            client_id,
            report=result.get("report") or [],
            new_count=result.get("new_count", 0),
            total=result.get("total", 0),
        )
        new_ids = [j.get("id") for j in result.get("new_jobs") or [] if j.get("id")]
        digest = await build_job_digest(client_id, new_job_ids=new_ids)

        _state.status = "done"
        _state.partial = {}
        _state.result = {
            "new_count": result["new_count"],
            "total": result["total"],
            "report": result["report"],
            "quality": result.get("quality"),
            "cross_verify": cross_stats,
            "organize": organize_stats,
            "jobs": list_jobs(client_id),
            "digest": digest,
            "crawl_health": health,
        }
        _state.progress = f"更新完成 · 共 {result['total']} 条"
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
