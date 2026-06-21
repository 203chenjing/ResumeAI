def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "AI 简历修改 API"
