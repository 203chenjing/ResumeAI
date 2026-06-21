"""知识库 AI 构建服务测试。"""
from __future__ import annotations

import pytest

from app.services import knowledge_builder as kb


@pytest.mark.asyncio
async def test_init_from_resume_strips_fence(monkeypatch):
    async def fake_chat_text(_sys, _user, **kwargs):
        return "```markdown\n## 项目\n- 事实 [待确认]\n```"

    monkeypatch.setattr(kb.client, "chat_text", fake_chat_text)
    out = await kb.init_from_resume("# 简历\n经历", "")
    assert "## 项目" in out
    assert "[待确认]" in out


@pytest.mark.asyncio
async def test_audit_knowledge_pending(monkeypatch):
    async def fake_chat_json(_sys, _user, **kwargs):
        return {"issues": ["缺量化指标"], "pending_count": 2, "summary": "有 2 处待确认"}

    monkeypatch.setattr(kb.client, "chat_json", fake_chat_json)
    result = await kb.audit_knowledge("## A\n- x [待确认]\n- y [待确认]")
    assert result["pending_count"] == 2
    assert "待确认" in result["summary"] or result["issues"]


@pytest.mark.asyncio
async def test_expand_star(monkeypatch):
    async def fake_chat_text(_sys, _user, **kwargs):
        return "Situation: …\nTask: …\nAction: …\nResult: 提升 30% [待确认]"

    monkeypatch.setattr(kb.client, "chat_text", fake_chat_text)
    out = await kb.expand_star("项目 A", "做了优化")
    assert "待确认" in out or "Result" in out


def test_parse_chat_response_with_kb_update():
    raw = """[CHAT_REPLY]
已整理实习项目素材。
[/CHAT_REPLY]
[KB_UPDATE]
## 实习/项目素材
- 携程 [待补充：API 数量]
[/KB_UPDATE]"""
    parsed = kb._parse_chat_response(raw)
    assert "已整理" in parsed["reply"]
    assert "携程" in parsed["updated_markdown"]


@pytest.mark.asyncio
async def test_chat_knowledge_returns_structured(monkeypatch):
    async def fake_chat_text(_sys, _user, **kwargs):
        return """[CHAT_REPLY]已更新指标清单[/CHAT_REPLY]
[KB_UPDATE]
## 指标清单
- API 12 个 [待确认]
[/KB_UPDATE]"""

    monkeypatch.setattr(kb.client, "chat_text", fake_chat_text)
    result = await kb.chat_knowledge("## 旧", "补全指标", ui_context={"selected_section_title": "指标清单"})
    assert result["updated_markdown"]
    assert result["ui_patch"].get("select_section_title") == "指标清单"
