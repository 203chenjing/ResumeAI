"""爬虫运行健康度持久化（对标 JobRadar site monitor）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HEALTH_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "crawl_health.json"


def _load_all() -> dict:
    if not HEALTH_PATH.exists():
        return {}
    try:
        return json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all(data: dict) -> None:
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_crawl_run(client_id: str, *, report: list[dict], new_count: int, total: int) -> dict:
    all_data = _load_all()
    now = datetime.now().isoformat()
    providers: dict[str, dict] = {}
    for item in report:
        name = item.get("provider", "unknown")
        status = item.get("status", "unknown")
        providers[name] = {
            "status": status,
            "fetched": item.get("fetched", 0),
            "duration_ms": item.get("duration_ms", 0),
            "error": item.get("error", ""),
            "last_run_at": now,
            "health": _status_color(status),
        }

    entry = {
        "last_run_at": now,
        "new_count": new_count,
        "total": total,
        "providers": providers,
        "summary": _summarize(providers),
    }
    all_data[client_id] = entry
    _save_all(all_data)
    return entry


def get_crawl_health(client_id: str = "default") -> dict:
    all_data = _load_all()
    return all_data.get(client_id) or {"summary": "unknown", "providers": {}, "last_run_at": ""}


def _status_color(status: str) -> str:
    if status == "ok":
        return "green"
    if status in ("skipped",):
        return "yellow"
    return "red"


def _summarize(providers: dict[str, dict]) -> str:
    if not providers:
        return "unknown"
    reds = sum(1 for p in providers.values() if p.get("health") == "red")
    greens = sum(1 for p in providers.values() if p.get("health") == "green")
    if reds == 0:
        return "healthy"
    if greens == 0:
        return "degraded"
    return "partial"
