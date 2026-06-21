def test_knowledge_template(client):
    r = client.get("/api/knowledge-base/template")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    template = body.get("data", {}).get("template", "")
    assert "STAR" in template or "待确认" in template


def test_user_memory_crud(client, tmp_user_memory):
    cid = "pytest_client"
    r = client.put(
        "/api/user-memory",
        json={"client_id": cid, "knowledge_base_md": "测试知识库", "notes": "note"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

    r2 = client.get(f"/api/user-memory/{cid}")
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["knowledge_base_md"] == "测试知识库"


def test_session_not_found(client):
    r = client.get("/api/session/nonexistent_session_id_000")
    assert r.status_code == 404
