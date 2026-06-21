import pytest

from app.services.pending_knowledge import (
    confirm_pending,
    extract_pending_from_diff,
    list_pending,
    merge_confirmed_into_kb,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.services.pending_knowledge as pk

    d = tmp_path / "pending"
    monkeypatch.setattr(pk, "DATA_DIR", d)
    return "test_client"


def test_extract_and_confirm(client):
    entry = extract_pending_from_diff(
        client_id=client,
        source="test",
        original_text="原文",
        new_text="优化后的量化描述",
    )
    assert entry is not None
    pending = list_pending(client)
    assert len(pending) == 1
    confirm_pending(client, entry["id"], "confirm")
    assert list_pending(client) == []
    kb = merge_confirmed_into_kb("", client)
    assert "优化后的量化" in kb
