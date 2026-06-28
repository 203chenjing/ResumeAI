"""北极星漏斗埋点：发现→改稿→导出→投递 闭环。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

FUNNEL_STEPS = (
    "job_view",
    "job_tailor_start",
    "studio_prepare",
    "match_analyzed",
    "suggestion_accept",
    "export_pdf",
    "apply_marked",
    "loop_complete",
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "funnel_metrics"


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


def _save(client_id: str, events: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path(client_id).write_text(json.dumps(events[-1000:], ensure_ascii=False, indent=2), encoding="utf-8")


def record_funnel_event(client_id: str, step: str, *, meta: dict | None = None) -> None:
    if step not in FUNNEL_STEPS:
        return
    events = _load(client_id)
    events.append({"step": step, "meta": meta or {}, "at": datetime.now().isoformat()})
    _save(client_id, events)


def funnel_summary(client_id: str, *, days: int = 7) -> dict:
    events = _load(client_id)
    cutoff = datetime.now().timestamp() - days * 86400
    recent = []
    for e in events:
        try:
            if datetime.fromisoformat(e["at"]).timestamp() >= cutoff:
                recent.append(e)
        except Exception:
            continue

    counts = Counter(e["step"] for e in recent)
    views = counts.get("job_view", 0)
    tailors = counts.get("job_tailor_start", 0) + counts.get("studio_prepare", 0)
    exports = counts.get("export_pdf", 0)
    applies = counts.get("apply_marked", 0)
    loops = counts.get("loop_complete", 0)

    return {
        "period_days": days,
        "total_events": len(recent),
        "by_step": dict(counts),
        "north_star_loops": loops,
        "conversion": {
            "view_to_tailor": round(tailors / max(views, 1), 3),
            "tailor_to_export": round(exports / max(tailors, 1), 3),
            "export_to_apply": round(applies / max(exports, 1), 3),
        },
    }
