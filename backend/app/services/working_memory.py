"""L3 工作记忆：任务级进度 / 偏移 / 投机缓存。"""
from __future__ import annotations

from app.models.schemas import Session


def default_working_memory(goal: str = "") -> dict:
    return {
        "goal": goal,
        "current_step": "",
        "completed_steps": [],
        "speculation": {},
        "checkpoint": {},
        "updated_at": None,
    }


def get_working_memory(sess: Session) -> dict:
    wm = getattr(sess, "working_memory", None)
    if not isinstance(wm, dict) or not wm:
        return default_working_memory()
    return wm


def update_working_memory(
    sess: Session,
    *,
    goal: str | None = None,
    current_step: str | None = None,
    completed_step: str | None = None,
    speculation: dict | None = None,
    checkpoint: dict | None = None,
) -> dict:
    from datetime import datetime

    wm = get_working_memory(sess)
    if goal is not None:
        wm["goal"] = goal
    if current_step is not None:
        wm["current_step"] = current_step
    if completed_step and completed_step not in wm.get("completed_steps", []):
        wm.setdefault("completed_steps", []).append(completed_step)
    if speculation is not None:
        wm["speculation"] = speculation
    if checkpoint is not None:
        wm["checkpoint"] = {**wm.get("checkpoint", {}), **checkpoint}
    wm["updated_at"] = datetime.now().isoformat()
    sess.working_memory = wm
    return wm


def working_memory_context(sess: Session) -> str:
    wm = get_working_memory(sess)
    if not any([wm.get("goal"), wm.get("current_step"), wm.get("completed_steps")]):
        return ""
    lines = ["==== L3 工作记忆（任务进度）===="]
    if wm.get("goal"):
        lines.append(f"目标: {wm['goal']}")
    if wm.get("current_step"):
        lines.append(f"当前步骤: {wm['current_step']}")
    if wm.get("completed_steps"):
        lines.append(f"已完成: {', '.join(wm['completed_steps'])}")
    if wm.get("speculation"):
        lines.append(f"投机缓存: {wm['speculation']}")
    if wm.get("checkpoint"):
        lines.append(f"检查点: {wm['checkpoint']}")
    lines.append("==== L3 结束 ====")
    return "\n".join(lines)
