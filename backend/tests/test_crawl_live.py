"""真实爬虫集成测试（需要网络 + Playwright）。"""
import os
import pytest

from app.services.job_feed import crawl_all


@pytest.mark.skipif(os.getenv("RUN_LIVE_CRAWL") != "1", reason="set RUN_LIVE_CRAWL=1 to run")
@pytest.mark.asyncio
async def test_live_crawl_returns_jobs():
    client_id = "live_crawl_test"
    result = await crawl_all(client_id, ["company_campus"])
    assert result["new_count"] >= 1, result.get("report")
    report = result.get("report") or []
    assert any(r.get("status") == "ok" for r in report)
