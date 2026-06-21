"""知识库 Agent API 测试。"""
from __future__ import annotations

from app.services.session_store import store


def test_init_from_resume_requires_session(client):
    r = client.post("/api/knowledge-agent/init-from-resume", json={"client_id": "t", "session_id": ""})
    assert r.status_code == 400


def test_init_from_resume_404_session(client):
    r = client.post(
        "/api/knowledge-agent/init-from-resume",
        json={"client_id": "t", "session_id": "nonexistent_xyz"},
    )
    assert r.status_code == 400


def test_init_from_resume_ok(client, monkeypatch, tmp_user_memory):
    sess = store.create()
    sess.current_resume_md = "# 张三\n## 经历\n- 做过后端开发"
    store.update(sess)

    async def fake_init(_sid, _cid=""):
        return "## 导入\n- 后端开发 [待确认]"

    import app.routers.knowledge_agent as router_mod

    monkeypatch.setattr(router_mod, "init_from_session", fake_init)

    r = client.post(
        "/api/knowledge-agent/init-from-resume",
        json={"client_id": "pytest_kb", "session_id": sess.session_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "待确认" in body["data"]["markdown"]


def test_audit_empty_content(client):
    r = client.post("/api/knowledge-agent/audit", json={"content": ""})
    assert r.status_code == 400


def test_chat_empty_message(client):
    r = client.post(
        "/api/knowledge-agent/chat",
        json={"client_id": "t", "content": "kb", "message": ""},
    )
    assert r.status_code == 400


def test_chat_persists_update(client, monkeypatch, tmp_user_memory):
    async def fake_chat(_kb, _msg, _hist=None, **kwargs):
        return {
            "reply": "已整理",
            "updated_markdown": "## 新\n- 事实",
            "ui_patch": {"focus_panel": "topics"},
        }

    import app.routers.knowledge_agent as router_mod

    monkeypatch.setattr(router_mod, "chat_knowledge", fake_chat)

    r = client.post(
        "/api/knowledge-agent/chat",
        json={
            "client_id": "pytest_kb_chat",
            "content": "## 旧",
            "message": "整理一下",
            "session_id": "",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["saved"] is True
    assert "## 新" in body["data"]["updated_markdown"]
