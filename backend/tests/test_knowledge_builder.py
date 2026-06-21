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


def test_parse_chat_response_unclosed_kb_update():
    raw = """[CHAT_REPLY]已添加项目经历[/CHAT_REPLY]
[KB_UPDATE]
## 实习 / 项目素材
### 新公司 · 开发 · 2024.01-2024.06
- Situation: [待补充：背景]
"""
    parsed = kb._parse_chat_response(raw)
    assert "新公司" in parsed["updated_markdown"]


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


def test_find_changed_heading_new_project():
    old = "## 实习 / 项目素材\n### 旧项目"
    new = "## 实习 / 项目素材\n### 旧项目\n### 新公司 · 岗位"
    assert kb._find_changed_heading(old, new, None) == "新公司 · 岗位"


def test_bundle_preserves_user_message():
    long_kb = "x" * 9000
    bundled = kb._bundle_chat_prompt(
        long_kb,
        "请添加一段项目经历",
        [{"role": "user", "content": "之前的话"}],
        {"selected_section_title": "实习"},
    )
    assert bundled.endswith("user: 请添加一段项目经历")
    assert "请添加一段项目经历" in bundled


@pytest.mark.asyncio
async def test_chat_knowledge_merges_fragment(monkeypatch):
    async def fake_chat_text(_sys, _user, **kwargs):
        return """[CHAT_REPLY]已添加[/CHAT_REPLY]
[KB_UPDATE]
### 测试公司 · 工程师 · 2024.01-2024.03
- Action: [待补充：做了什么]
[/KB_UPDATE]"""

    monkeypatch.setattr(kb.client, "chat_text", fake_chat_text)
    old = "## 实习 / 项目素材\n### 旧项目\n- 事实"
    result = await kb.chat_knowledge(old, "添加项目", ui_context={})
    assert "测试公司" in result["updated_markdown"]
    assert "旧项目" in result["updated_markdown"]


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
