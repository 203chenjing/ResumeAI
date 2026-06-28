"""用户行为信号：投递/改稿/点击 → 个性化排序飞轮（零 token）。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "behavior_signals"

EVENT_TYPES = frozenset(
    {"view_job", "tailor_start", "export_pdf", "apply_mark", "dismiss_job", "compare_jobs"}
)


def _path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DATA_DIR / f"{safe}.json"


def _load(client_id: str) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(client_id)
    if not p.exists():
        return {"events": [], "steer": {"boost_companies": [], "boost_cities": [], "block_companies": []}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"events": [], "steer": {"boost_companies": [], "boost_cities": [], "block_companies": []}}
        raw.setdefault("events", [])
        raw.setdefault("steer", {"boost_companies": [], "boost_cities": [], "block_companies": []})
        return raw
    except Exception:
        return {"events": [], "steer": {"boost_companies": [], "boost_cities": [], "block_companies": []}}


def _save(client_id: str, data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path(client_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_event(
    client_id: str,
    event_type: str,
    *,
    job_id: str = "",
    company: str = "",
    role: str = "",
    meta: dict | None = None,
) -> None:
    if event_type not in EVENT_TYPES:
        return
    data = _load(client_id)
    events = data.get("events") or []
    events.append(
        {
            "type": event_type,
            "job_id": job_id,
            "company": company,
            "role": role,
            "meta": meta or {},
            "at": datetime.now().isoformat(),
        }
    )
    data["events"] = events[-500:]
    _save(client_id, data)


def update_steer(
    client_id: str,
    *,
    boost_companies: list[str] | None = None,
    boost_cities: list[str] | None = None,
    block_companies: list[str] | None = None,
) -> dict:
    data = _load(client_id)
    steer = data.setdefault("steer", {})
    if boost_companies is not None:
        steer["boost_companies"] = [c.strip() for c in boost_companies if c.strip()][:20]
    if boost_cities is not None:
        steer["boost_cities"] = [c.strip() for c in boost_cities if c.strip()][:10]
    if block_companies is not None:
        steer["block_companies"] = [c.strip() for c in block_companies if c.strip()][:20]
    _save(client_id, data)
    return steer


def _learn_from_applications(client_id: str) -> dict:
    from app.services.application_store import list_applications

    apps = list_applications(client_id)
    applied_cos: Counter[str] = Counter()
    rejected_cos: Counter[str] = Counter()
    cities: Counter[str] = Counter()

    for a in apps:
        co = (a.get("company") or "").strip()
        st = a.get("status", "")
        if not co:
            continue
        if st in ("Applied", "WrittenTest", "Interview", "Offer"):
            applied_cos[co] += 2
        elif st == "Rejected":
            rejected_cos[co] += 1
        for part in (a.get("notes") or "").split():
            for c in ("北京", "上海", "深圳", "杭州", "广州", "成都", "武汉", "南京"):
                if c in part:
                    cities[c] += 1

    return {
        "applied_companies": [c for c, _ in applied_cos.most_common(8)],
        "rejected_companies": [c for c, _ in rejected_cos.most_common(5)],
        "inferred_cities": [c for c, _ in cities.most_common(4)],
    }


def get_behavior_profile(client_id: str) -> dict:
    data = _load(client_id)
    learned = _learn_from_applications(client_id)
    steer = data.get("steer") or {}
    events = data.get("events") or []

    tailored_jobs = {e["job_id"] for e in events if e.get("type") == "tailor_start" and e.get("job_id")}
    dismissed = {e["job_id"] for e in events if e.get("type") == "dismiss_job" and e.get("job_id")}

    return {
        "steer": steer,
        "learned": learned,
        "tailored_job_ids": list(tailored_jobs)[:50],
        "dismissed_job_ids": list(dismissed)[:50],
        "event_count": len(events),
    }


def behavior_boost_for_job(job: dict, profile: dict | None) -> tuple[float, list[str]]:
    """返回 [0, 0.2] 的行为加分与可解释理由。"""
    if not profile:
        return 0.0, []
    reasons: list[str] = []
    bonus = 0.0
    blob = f"{job.get('company', '')} {job.get('role', '')} {job.get('location', '')}"
    steer = profile.get("steer") or {}
    learned = profile.get("learned") or {}

    for c in steer.get("boost_companies") or []:
        if c and c in blob:
            bonus += 0.08
            reasons.append(f"你标记偏好公司「{c}」")
            break
    for city in (steer.get("boost_cities") or []) + (learned.get("inferred_cities") or []):
        if city and city in blob:
            bonus += 0.05
            reasons.append(f"与你常投城市「{city}」一致")
            break
    for c in learned.get("applied_companies") or []:
        if c and c in (job.get("company") or ""):
            bonus += 0.06
            reasons.append(f"你曾投递过「{c}」同类岗位")
            break
    for c in (steer.get("block_companies") or []) + (learned.get("rejected_companies") or []):
        if c and c in (job.get("company") or ""):
            return -0.5, [f"已标记回避「{c}」"]

    jid = job.get("id", "")
    if jid and jid in (profile.get("dismissed_job_ids") or []):
        bonus -= 0.15
        reasons.append("你曾划走过此岗位")

    return min(bonus, 0.2), reasons[:3]
