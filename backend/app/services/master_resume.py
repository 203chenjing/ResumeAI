"""母版简历存储：对标 Resume-Matcher Master Resume。"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "master_resumes"


def _path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DATA_DIR / f"{safe}.json"


def _load_all(client_id: str) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(client_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_all(client_id: str, items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path(client_id).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_masters(client_id: str) -> list[dict]:
    return _load_all(client_id)


def get_master(client_id: str, master_id: str) -> dict | None:
    for m in _load_all(client_id):
        if m.get("id") == master_id:
            return m
    return None


def get_active_master(client_id: str) -> dict | None:
    items = _load_all(client_id)
    for m in items:
        if m.get("is_active"):
            return m
    return items[0] if items else None


def save_master(
    client_id: str,
    markdown: str,
    *,
    title: str = "母版简历",
    knowledge_hash: str = "",
    set_active: bool = True,
) -> dict:
    items = _load_all(client_id)
    kb_hash = knowledge_hash or hashlib.sha256(markdown.encode()).hexdigest()[:16]
    now = datetime.now().isoformat()

    if set_active:
        for m in items:
            m["is_active"] = False

    master = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "markdown": markdown,
        "knowledge_hash": kb_hash,
        "resume_facts_locked": True,
        "is_active": set_active,
        "created_at": now,
        "updated_at": now,
    }
    items.insert(0, master)
    _save_all(client_id, items[:20])
    return master
