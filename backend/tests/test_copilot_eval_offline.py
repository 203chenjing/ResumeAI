"""离线 plumbing 测试（CI 安全）：mock DeepSeek，验证 eval runner 正确捕获工具调用与产出。

不依赖 deepeval、不需要 API key —— 它检验的是 harness 管线本身，而非真实模型的工具选择。
真实模型的工具正确率由 evals/test_copilot_tooluse.py（需 key）评测。
"""
import json

import pytest

from app.services import career_copilot
from evals.runner import make_fixture_context, run_copilot


def _scripted_llm(tool_name: str, args: dict):
    """返回一个 fake chat_with_tools：第一轮调指定工具，第二轮给结论。"""
    state = {"n": 0}

    async def fake(messages, tools, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": json.dumps(args)},
                    }
                ],
            }
        return {"role": "assistant", "content": "这是结论。"}

    return fake


def test_runner_captures_search_tool(monkeypatch):
    monkeypatch.setattr(
        career_copilot.client, "chat_with_tools", _scripted_llm("search_jobs", {"city": "北京"})
    )
    res = run_copilot("北京有什么岗位", ctx=make_fixture_context())
    assert res.tool_names == ["search_jobs"]
    assert "job_cards" in res.block_types
    assert res.reply == "这是结论。"


def test_runner_captures_rerank_tool(monkeypatch):
    monkeypatch.setattr(
        career_copilot.client, "chat_with_tools", _scripted_llm("rerank_by_resume", {"top_k": 3})
    )
    res = run_copilot("最适合我的岗位", ctx=make_fixture_context())
    assert res.tool_names == ["rerank_by_resume"]
    assert "job_cards" in res.block_types


def test_runner_multi_tool_sequence(monkeypatch):
    """两轮工具：search 后 get_job_detail，再出结论。"""
    state = {"n": 0}

    async def fake(messages, tools, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "a", "type": "function", "function": {"name": "search_jobs", "arguments": json.dumps({"city": "北京"})}},
                ],
            }
        if state["n"] == 2:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "b", "type": "function", "function": {"name": "get_job_detail", "arguments": json.dumps({"job_id": "j1"})}},
                ],
            }
        return {"role": "assistant", "content": "字节跳动后端实习适合你。"}

    monkeypatch.setattr(career_copilot.client, "chat_with_tools", fake)
    res = run_copilot("北京后端实习的细节", ctx=make_fixture_context())
    assert res.tool_names == ["search_jobs", "get_job_detail"]
    assert "字节跳动" in res.reply
