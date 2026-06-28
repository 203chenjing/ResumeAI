"""跟进提醒：对标 career-ops followup-cadence + 岗位库截止日。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.application_store import list_applications
from app.services.today_briefing import build_today_briefing


def followup_reminders(client_id: str) -> list[dict]:
    apps = list_applications(client_id)
    now = datetime.now()
    reminders: list[dict] = []

    for a in apps:
        deadline = a.get("deadline", "")
        if deadline:
            try:
                dl = datetime.fromisoformat(deadline.replace("Z", ""))
                days = (dl - now).days
                if 0 <= days <= 7:
                    reminders.append(
                        {
                            "type": "deadline",
                            "app_id": a["id"],
                            "company": a.get("company", ""),
                            "role": a.get("role", ""),
                            "message": f"截止日还有 {days} 天",
                            "urgency": "high" if days <= 2 else "medium",
                            "due_at": deadline,
                        }
                    )
            except ValueError:
                pass

        status = a.get("status", "")
        updated = a.get("updated_at", "")
        if status in ("Applied", "WrittenTest") and updated:
            try:
                upd = datetime.fromisoformat(updated.replace("Z", ""))
                if now - upd > timedelta(days=14):
                    reminders.append(
                        {
                            "type": "followup",
                            "app_id": a["id"],
                            "company": a.get("company", ""),
                            "role": a.get("role", ""),
                            "message": "已投递超过 14 天，建议跟进或更新状态",
                            "urgency": "low",
                            "due_at": updated,
                        }
                    )
            except ValueError:
                pass

    # 岗位库截止日（未投递的高匹配岗）
    try:
        briefing = build_today_briefing(client_id)
        for u in briefing.get("urgent_deadlines") or []:
            reminders.append(
                {
                    "type": "job_deadline",
                    "job_id": u.get("job_id"),
                    "company": u.get("company", ""),
                    "role": u.get("role", ""),
                    "message": u.get("message", "岗位即将截止"),
                    "urgency": "high" if (u.get("days_left") or 99) <= 1 else "medium",
                    "due_at": u.get("deadline", ""),
                    "action": "tailor",
                }
            )
    except Exception:
        pass

    reminders.sort(key=lambda r: (0 if r["urgency"] == "high" else 1 if r["urgency"] == "medium" else 2))
    return reminders
