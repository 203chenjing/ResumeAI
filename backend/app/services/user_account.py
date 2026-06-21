"""用户账号档案：扩展 client_id 为可配置用户。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "users"

DEFAULT_PROFILE = {
    "display_name": "",
    "email": "",
    "school": "",
    "major": "",
    "graduation_year": "",
    "target_roles": [],
    "weekly_apply_limit": 15,
    "min_match_score": 60,
    "created_at": "",
    "updated_at": "",
}


def _path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DATA_DIR / f"{safe}.json"


def get_profile(client_id: str) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(client_id)
    if not p.exists():
        now = datetime.now().isoformat()
        profile = {**DEFAULT_PROFILE, "client_id": client_id, "created_at": now, "updated_at": now}
        return profile
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        merged = {**DEFAULT_PROFILE, **data}
        merged["client_id"] = client_id
        return merged
    except Exception:
        return {**DEFAULT_PROFILE, "client_id": client_id}


def save_profile(client_id: str, payload: dict) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = get_profile(client_id)
    for key in DEFAULT_PROFILE:
        if key in payload:
            current[key] = payload[key]
    current["updated_at"] = datetime.now().isoformat()
    if not current.get("created_at"):
        current["created_at"] = current["updated_at"]
    _path(client_id).write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current
