"""后台爬虫任务测试。"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.crawl_task import get_crawl_state, start_crawl


@pytest.mark.asyncio
async def test_start_crawl_returns_running_without_blocking():
    with (
        patch("app.services.job_feed.crawl_all", new_callable=AsyncMock) as mock_crawl,
        patch("app.services.crawl_health.record_crawl_run") as mock_health,
        patch("app.services.job_digest.build_job_digest", new_callable=AsyncMock) as mock_digest,
        patch("app.services.job_feed.list_jobs", return_value=[]),
    ):
        mock_crawl.return_value = {
            "new_jobs": [],
            "new_count": 0,
            "total": 0,
            "report": [],
            "quality": {},
        }
        mock_health.return_value = {"ok": True}
        mock_digest.return_value = {"summary": "test"}

        state = await start_crawl("test_client", ["company_campus"])
        assert state.status == "running"

        # 等待后台任务结束
        for _ in range(50):
            await asyncio.sleep(0.05)
            done = await get_crawl_state()
            if done.status in ("done", "error"):
                break
        final = await get_crawl_state()
        assert final.status == "done"
        assert final.result is not None
        mock_crawl.assert_awaited_once()
