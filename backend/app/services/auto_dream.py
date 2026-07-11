"""L6 休眠重塑：AutoDream 离线记忆整合。"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.services import memdir

logger = logging.getLogger(__name__)

SESSION_MEMORY_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "session_memory"


def _hours_since(iso_ts: str | None) -> float:
    if not iso_ts:
        return float("inf")
    try:
        then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - then
        return delta.total_seconds() / 3600
    except ValueError:
        return float("inf")


def dream_status(client_id: str = "default") -> dict:
    state = memdir.get_dream_state(client_id)
    min_hours = getattr(settings, "autodream_min_hours", 24)
    min_sessions = getattr(settings, "autodream_min_sessions", 5)
    hours = _hours_since(state.get("last_consolidation_at"))
    sessions = state.get("sessions_since_consolidation", 0)
    time_ok = hours >= min_hours
    session_ok = sessions >= min_sessions
    return {
        "client_id": client_id,
        "last_consolidation_at": state.get("last_consolidation_at"),
        "sessions_since_consolidation": sessions,
        "total_consolidations": state.get("total_consolidations", 0),
        "hours_since_last": round(hours, 1) if hours != float("inf") else None,
        "gates": {
            "time": {"required_hours": min_hours, "passed": time_ok},
            "sessions": {"required": min_sessions, "passed": session_ok},
        },
        "ready": time_ok and session_ok,
    }


def should_trigger(client_id: str = "default") -> bool:
    return dream_status(client_id)["ready"]


def _dedupe_index_lines(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        key = line.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return "\n".join(out) + "\n"


def _compress_long_index_lines(text: str, max_chars: int = 200) -> str:
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("- [") and len(line) > max_chars:
            match = re.match(r"(- \[[^\]]+\]\([^)]+\)): (.+)", line)
            if match:
                out.append(f"{match.group(1)}: {match.group(2)[:max_chars - 20]}…")
                continue
        out.append(line)
    return "\n".join(out) + "\n"


def _merge_session_archives(client_id: str) -> list[str]:
    """收集近期会话摘要中的岗位/偏好线索，供写入 logs。"""
    hints: list[str] = []
    if not SESSION_MEMORY_ROOT.is_dir():
        return hints
    root = memdir.ensure_memdir(client_id)
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for summary_file in sorted(SESSION_MEMORY_ROOT.glob("*/summary.md"))[-10:]:
        try:
            text = summary_file.read_text(encoding="utf-8")
            if "目标岗位" in text:
                hints.append(text[:400])
        except OSError:
            continue
    if hints:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = logs / f"{stamp}-session-hints.md"
        log_path.write_text("\n\n---\n\n".join(hints), encoding="utf-8")
    return hints


def consolidate(client_id: str = "default", *, force: bool = False) -> dict:
    """执行休眠重塑：去重索引、压缩长行、归档会话摘要。"""
    status = dream_status(client_id)
    if not force and not status["ready"]:
        return {"success": False, "reason": "gates_not_passed", "status": status}

    if not memdir.acquire_consolidation_lock(client_id):
        return {"success": False, "reason": "lock_held", "status": status}

    actions: list[str] = []
    try:
        memdir.ensure_memdir(client_id)
        index_text = memdir.read_index(client_id)
        cleaned = _dedupe_index_lines(_compress_long_index_lines(index_text))
        if cleaned != index_text:
            memdir._write_index_safe(client_id, cleaned)
            actions.append("index_deduped")

        archived = _merge_session_archives(client_id)
        if archived:
            actions.append(f"archived_{len(archived)}_session_hints")

        state = memdir.get_dream_state(client_id)
        state["last_consolidation_at"] = datetime.now(timezone.utc).isoformat()
        state["sessions_since_consolidation"] = 0
        state["total_consolidations"] = state.get("total_consolidations", 0) + 1
        memdir.save_dream_state(client_id, state)
        actions.append("state_reset")

        return {
            "success": True,
            "actions": actions,
            "status": dream_status(client_id),
        }
    except Exception as e:
        logger.exception("auto_dream consolidate failed")
        return {"success": False, "reason": str(e), "status": status}
    finally:
        memdir.release_consolidation_lock(client_id)
