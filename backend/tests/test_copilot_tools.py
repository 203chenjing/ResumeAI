import json

import pytest

from app.services import career_copilot
from app.services.copilot_tools import TOOLS, CopilotContext, run_tool


JOBS = [
    {
        "id": "j1",
        "company": "字节跳动",
        "role": "后端开发实习",
        "job_type": "实习",
        "location": "北京",
        "locations": ["北京"],
        "jd_url": "https://jobs.bytedance.com/1",
        "jd_text": "Python 后端 实习 北京 微服务",
        "source": "github_joblist",
        "referral_code": "AB12CD",
    },
    {
        "id": "j2",
        "company": "腾讯",
        "role": "前端开发",
        "job_type": "校招",
        "location": "深圳",
        "locations": ["深圳"],
        "jd_url": "https://careers.tencent.com/2",
        "jd_text": "React 前端 校招 深圳",
        "source": "github_joblist",
    },
]


def _ctx(resume="Python 后端 微服务 经验丰富", jobs=None, prefs=None):
    return CopilotContext(
        client_id="t",
        _jobs=jobs if jobs is not None else JOBS,
        _resume=resume,
        _prefs=prefs or {"target_cities": ["北京"]},
    )


def test_tools_schema_wellformed():
    names = {t["function"]["name"] for t in TOOLS}
    assert {"search_jobs", "rerank_by_resume", "get_daily_digest", "compare_jobs", "get_job_detail", "get_preferences"} <= names
    for t in TOOLS:
        assert t["type"] == "function"
        assert "parameters" in t["function"]


def test_search_jobs_by_city():
    res = run_tool(_ctx(), "search_jobs", {"city": "北京"})
    assert res["result"]["total"] == 1
    assert res["result"]["jobs"][0]["company"] == "字节跳动"
    assert res["blocks"][0]["type"] == "job_cards"


def test_search_jobs_by_query():
    res = run_tool(_ctx(), "search_jobs", {"query": "前端"})
    assert res["result"]["total"] == 1
    assert res["result"]["jobs"][0]["company"] == "腾讯"


def test_rerank_requires_resume():
    res = run_tool(_ctx(resume=""), "rerank_by_resume", {})
    assert res["result"]["error"] == "no_resume"
    assert res["blocks"][0]["type"] == "actions"


def test_rerank_with_resume_returns_scores():
    res = run_tool(_ctx(), "rerank_by_resume", {"top_k": 2})
    jobs = res["result"]["jobs"]
    assert len(jobs) == 2
    assert all("score" in j for j in jobs)
    assert any(b["type"] == "job_cards" for b in res["blocks"])


def test_get_job_detail():
    res = run_tool(_ctx(), "get_job_detail", {"job_id": "j1"})
    assert res["result"]["company"] == "字节跳动"
    assert res["result"]["referral_code"] == "AB12CD"
    assert "jd_text" in res["result"]


def test_get_job_detail_not_found():
    res = run_tool(_ctx(), "get_job_detail", {"job_id": "nope"})
    assert res["result"]["error"] == "not_found"


def test_compare_needs_two():
    res = run_tool(_ctx(), "compare_jobs", {"job_ids": ["j1"]})
    assert res["result"]["error"] == "need_two"


def test_get_preferences():
    res = run_tool(_ctx(), "get_preferences", {})
    assert res["result"]["target_cities"] == ["北京"]


def test_unknown_tool():
    res = run_tool(_ctx(), "frobnicate", {})
    assert res["result"]["error"] == "unknown_tool"


@pytest.mark.asyncio
async def test_tool_calling_loop(monkeypatch):
    """模拟 DeepSeek：第一轮调用 search_jobs，第二轮给出文字结论。"""
    calls = {"n": 0}

    async def fake_chat_with_tools(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "search_jobs", "arguments": json.dumps({"city": "北京"})},
                    }
                ],
            }
        return {"role": "assistant", "content": "北京有字节跳动后端实习，建议优先投递。"}

    monkeypatch.setattr(career_copilot.client, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(career_copilot.settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr(
        career_copilot, "CopilotContext", lambda client_id: _ctx()
    )

    events = []
    async for ev in career_copilot.stream_career_copilot("t", "北京有什么岗位"):
        events.append(ev)

    types = [e["type"] for e in events]
    assert "text" in types
    assert "done" in types
    done = next(e for e in events if e["type"] == "done")
    assert "字节跳动" in done["reply"]
    assert any(b["type"] == "job_cards" for b in done["blocks"])
    assert calls["n"] == 2
