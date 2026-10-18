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
    confirm_pending(client, entry["id"], "confirm", "携程 · 产品实习")
    assert list_pending(client) == []
    kb = merge_confirmed_into_kb("", client)
    assert "### 携程 · 产品实习" in kb
    assert "优化后的量化" in kb


def test_confirm_requires_target_title(client):
    """确认必须选归属经历，否则素材无处归档。"""
    entry = extract_pending_from_diff(
        client_id=client,
        source="test",
        original_text="原文",
        new_text="优化后的量化描述",
    )
    assert entry is not None

    with pytest.raises(ValueError, match="归属经历"):
        confirm_pending(client, entry["id"], "confirm")

    # 失败后条目仍是 pending，不能被静默丢弃
    assert len(list_pending(client)) == 1


def test_ignore_without_title(client):
    entry = extract_pending_from_diff(
        client_id=client,
        source="test",
        original_text="原文",
        new_text="优化后的量化描述",
    )
    assert entry is not None
    confirm_pending(client, entry["id"], "ignore")
    assert list_pending(client) == []
