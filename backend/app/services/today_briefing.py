"""Hub 今日简报 + 30 秒 Aha：发现→匹配→行动 预计算。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.application_store import list_applications
from app.services.behavior_signals import get_behavior_profile
from app.services.job_digest import load_digest
from app.services.job_feed import list_jobs
from app.services.job_preferences import load_job_preferences
from app.services.job_readiness import compute_readiness, rank_jobs_with_readiness
from app.services.master_resume import get_active_master
from app.services.user_memory import load_memory


def _resume_md(client_id: str) -> str:
    master = get_active_master(client_id)
    if master and master.get("markdown"):
        return master["markdown"]
    return load_memory(client_id).get("knowledge_base_md", "") or ""


def _urgent_jobs(jobs: list[dict], apps: list[dict], *, within_days: int = 3) -> list[dict]:
    applied_cos = {(a.get("company") or "", a.get("role") or "") for a in apps}
    urgent: list[dict] = []
    now = datetime.now()
    for j in jobs:
        dl = (j.get("deadline") or "").strip()
        if not dl:
            continue
        try:
            parsed = datetime.fromisoformat(dl.replace("Z", "")[:10])
        except ValueError:
            continue
        days = (parsed - now).days
        if days < 0 or days > within_days:
            continue
        key = (j.get("company", ""), j.get("role", ""))
        if key in applied_cos:
            continue
        urgent.append({**j, "days_left": days})
    urgent.sort(key=lambda x: x.get("days_left", 99))
    return urgent[:5]


def build_today_briefing(client_id: str) -> dict:
    jobs = list_jobs(client_id, include_weak=False)
    resume = _resume_md(client_id)
    apps = list_applications(client_id)
    profile = get_behavior_profile(client_id)
    digest = load_digest(client_id)
    prefs = load_job_preferences(client_id)

    personalization = ""
    learned = profile.get("learned") or {}
    if learned.get("applied_companies"):
        personalization = f"根据你投递过的 {', '.join(learned['applied_companies'][:3])} 等，优先推荐同类岗位"
    elif prefs.get("target_cities"):
        personalization = f"已按偏好城市 {', '.join(prefs['target_cities'][:3])} 排序"

    top_picks: list[dict] = []
    if resume.strip():
        ranked = rank_jobs_with_readiness(client_id, jobs, resume, top_k=3)
        for row in ranked:
            j = row["job"]
            rd = row["readiness"]
            top_picks.append(
                {
                    "job_id": j.get("id"),
                    "company": j.get("company"),
                    "role": j.get("role"),
                    "readiness_score": rd.get("readiness_score"),
                    "match_score": rd.get("match_score"),
                    "deadline": j.get("deadline"),
                    "jd_url": j.get("jd_url"),
                    "referral_code": j.get("referral_code"),
                    "reasons": rd.get("reasons", [])[:3],
                    "next_action": rd.get("next_action"),
                }
            )
    elif digest and digest.get("priority_jobs"):
        for p in digest["priority_jobs"][:3]:
            top_picks.append(
                {
                    "job_id": p.get("job_id"),
                    "company": p.get("company"),
                    "role": p.get("role"),
                    "readiness_score": p.get("score"),
                    "match_score": p.get("score"),
                    "reasons": [p.get("ai_summary") or "今日摘要推荐"],
                    "next_action": "tailor",
                }
            )

    urgent = _urgent_jobs(jobs, apps)
    deadline_cards = []
    for j in urgent:
        rd = compute_readiness(j, resume_md=resume, client_id=client_id) if resume else {}
        deadline_cards.append(
            {
                "job_id": j.get("id"),
                "company": j.get("company"),
                "role": j.get("role"),
                "days_left": j.get("days_left"),
                "deadline": j.get("deadline"),
                "readiness_score": rd.get("readiness_score"),
                "jd_url": j.get("jd_url"),
                "referral_code": j.get("referral_code"),
                "message": f"还剩 {j.get('days_left')} 天截止，建议今日完成改稿投递",
            }
        )

    headline = "今天投什么"
    if deadline_cards:
        headline = f"⏰ {deadline_cards[0]['company']} 等 {len(deadline_cards)} 个岗位即将截止"
    elif top_picks:
        headline = f"为你选出 Top {len(top_picks)} 值得投的岗位"

    return {
        "headline": headline,
        "personalization_note": personalization,
        "has_resume": bool(resume.strip()),
        "feed_total": len(jobs),
        "top_picks": top_picks,
        "urgent_deadlines": deadline_cards,
        "digest_headline": (digest or {}).get("headline", ""),
        "generated_at": datetime.now().isoformat(),
    }


def build_aha_after_upload(client_id: str, resume_md: str) -> dict:
    """上传简历后 30 秒 Aha：立即给出 Top3 + 一句结论。"""
    jobs = list_jobs(client_id, include_weak=False)
    if not resume_md.strip() or not jobs:
        return {
            "headline": "简历已解析，去岗位页发现机会或粘贴 JD 开始改稿",
            "top_picks": [],
            "summary": "",
        }

    ranked = rank_jobs_with_readiness(client_id, jobs, resume_md, top_k=3)
    picks = []
    for row in ranked:
        j, rd = row["job"], row["readiness"]
        picks.append(
            {
                "job_id": j.get("id"),
                "company": j.get("company"),
                "role": j.get("role"),
                "readiness_score": rd.get("readiness_score"),
                "match_score": rd.get("match_score"),
                "referral_code": j.get("referral_code"),
                "jd_url": j.get("jd_url"),
                "reasons": rd.get("reasons", [])[:2],
            }
        )

    if not picks:
        return {"headline": "暂无高匹配岗位，可先完善求职偏好", "top_picks": [], "summary": ""}

    lead = picks[0]
    summary = (
        f"已读懂你的简历。今天最该优先看：{lead['company']}·{lead['role']}"
        f"（准备度 {lead['readiness_score']} 分）。"
    )
    if lead.get("referral_code"):
        summary += f" 含内推码 {lead['referral_code']}。"

    return {
        "headline": "为你找到最匹配的岗位",
        "top_picks": picks,
        "summary": summary,
    }
