"""岗位发现：用户求职偏好（与写作偏好分离存储）。"""
from __future__ import annotations

from app.services.user_memory import load_memory, save_memory

DEFAULT_JOB_PREFERENCES = {
    "target_roles": [],
    "target_cities": [],
    "job_types": ["实习", "校招"],
    "company_wishlist": [],
    "company_blocklist": [],
    "extra_notes": "",
}


def load_job_preferences(client_id: str) -> dict:
    mem = load_memory(client_id)
    raw = mem.get("job_preferences") or {}
    out = dict(DEFAULT_JOB_PREFERENCES)
    for key in DEFAULT_JOB_PREFERENCES:
        val = raw.get(key)
        if val is None:
            continue
        if key in ("target_roles", "target_cities", "job_types", "company_wishlist", "company_blocklist"):
            if isinstance(val, list):
                out[key] = [str(x).strip() for x in val if str(x).strip()]
            elif isinstance(val, str) and val.strip():
                out[key] = [p.strip() for p in val.replace("，", ",").split(",") if p.strip()]
        else:
            out[key] = str(val).strip()
    return out


def save_job_preferences(client_id: str, prefs: dict) -> dict:
    current = load_job_preferences(client_id)
    for key in DEFAULT_JOB_PREFERENCES:
        if key in prefs and prefs[key] is not None:
            current[key] = prefs[key]
    save_memory(client_id, {"job_preferences": current})
    return current
