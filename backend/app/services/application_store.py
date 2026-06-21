"""投递申请追踪：对标 career-ops applications + job-ops pipeline。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "applications"

STATUSES = (
    "Evaluated",
    "Applied",
    "WrittenTest",
    "Interview",
    "Offer",
    "Rejected",
    "Discarded",
    "SKIP",
)


def _path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DATA_DIR / f"{safe}.json"


def _load(client_id: str) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(client_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(client_id: str, apps: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path(client_id).write_text(
        json.dumps(apps, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_applications(client_id: str) -> list[dict]:
    return _load(client_id)


def create_application(client_id: str, payload: dict) -> dict:
    apps = _load(client_id)
    now = datetime.now().isoformat()
    app = {
        "id": uuid.uuid4().hex[:12],
        "company": payload.get("company", ""),
        "role": payload.get("role", ""),
        "channel": payload.get("channel", "官网"),
        "jd_text": payload.get("jd_text", ""),
        "jd_url": payload.get("jd_url", ""),
        "match_score": payload.get("match_score", 0),
        "decision_level": payload.get("decision_level", ""),
        "status": payload.get("status", "Evaluated"),
        "session_id": payload.get("session_id", ""),
        "resume_pdf_path": payload.get("resume_pdf_path", ""),
        "deadline": payload.get("deadline", ""),
        "notes": payload.get("notes", ""),
        "created_at": now,
        "updated_at": now,
        "status_history": [{"status": payload.get("status", "Evaluated"), "at": now}],
    }
    apps.append(app)
    _save(client_id, apps)
    return app


def update_status(client_id: str, app_id: str, status: str, notes: str = "") -> dict:
    if status not in STATUSES:
        raise ValueError(f"非法状态: {status}")
    apps = _load(client_id)
    for a in apps:
        if a.get("id") == app_id:
            now = datetime.now().isoformat()
            a["status"] = status
            a["updated_at"] = now
            if notes:
                a["notes"] = notes
            hist = a.get("status_history") or []
            hist.append({"status": status, "at": now})
            a["status_history"] = hist
            _save(client_id, apps)
            return a
    raise ValueError("申请不存在")


def delete_application(client_id: str, app_id: str) -> dict:
    apps = _load(client_id)
    for i, a in enumerate(apps):
        if a.get("id") == app_id:
            removed = apps.pop(i)
            _save(client_id, apps)
            return removed
    raise ValueError("申请不存在")


def funnel_stats(client_id: str) -> dict:
    apps = _load(client_id)
    total = len(apps)
    by_status: dict[str, int] = {}
    for a in apps:
        s = a.get("status", "Evaluated")
        by_status[s] = by_status.get(s, 0) + 1
    applied = by_status.get("Applied", 0) + by_status.get("WrittenTest", 0)
    interviewed = by_status.get("Interview", 0) + by_status.get("Offer", 0)
    rejected = by_status.get("Rejected", 0)
    evaluated = by_status.get("Evaluated", 0)
    written = by_status.get("WrittenTest", 0)
    interview_only = by_status.get("Interview", 0)
    return {
        "total": total,
        "by_status": by_status,
        "applied_count": applied,
        "interview_count": interviewed,
        "offer_count": by_status.get("Offer", 0),
        "rejected_count": rejected,
        "reply_rate": round(applied / max(total - evaluated, 1), 3),
        "written_test_rate": round(written / max(applied, 1), 3),
        "interview_rate": round(interview_only / max(applied, 1), 3),
        "offer_rate": round(by_status.get("Offer", 0) / max(interview_only + by_status.get("Offer", 0), 1), 3),
    }
