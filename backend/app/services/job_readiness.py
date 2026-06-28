"""投递准备度：一个 glanceable 数字 + 可解释排序。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.services.application_store import list_applications
from app.services.behavior_signals import behavior_boost_for_job, get_behavior_profile
from app.services.job_preferences import load_job_preferences
from app.services.match_engine import hybrid_match_score, rerank_jobs


def _parse_deadline(deadline: str) -> int | None:
    if not deadline:
        return None
    s = deadline.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            dl = datetime.strptime(s, fmt)
            return (dl - datetime.now()).days
        except ValueError:
            continue
    m = re.search(r"(\d{1,2})[./月](\d{1,2})", deadline)
    if m:
        try:
            dl = datetime(datetime.now().year, int(m.group(1)), int(m.group(2)))
            return (dl - datetime.now()).days
        except ValueError:
            pass
    return None


def _tailored_for_job(client_id: str, job_id: str, apps: list[dict]) -> bool:
    for a in apps:
        if a.get("job_id") == job_id or (
            a.get("session_id") and a.get("status") not in ("Discarded", "SKIP")
        ):
            if a.get("match_score", 0) > 0:
                return True
    return False


def compute_readiness(
    job: dict,
    *,
    resume_md: str,
    client_id: str,
    prefs: dict | None = None,
    apps: list[dict] | None = None,
    profile: dict | None = None,
) -> dict:
    prefs = prefs or load_job_preferences(client_id)
    apps = apps if apps is not None else list_applications(client_id)
    profile = profile if profile is not None else get_behavior_profile(client_id)

    jd_text = job.get("jd_text", "") or job.get("role", "")
    match, breakdown = hybrid_match_score(resume_md, jd_text, prefs=prefs)
    hybrid = breakdown.overall

    beh_boost, beh_reasons = behavior_boost_for_job(job, profile)
    if beh_boost < -0.3:
        readiness = 5
        return {
            "readiness_score": readiness,
            "match_score": hybrid,
            "components": {"match": hybrid, "behavior": int(beh_boost * 100)},
            "reasons": beh_reasons,
            "blockers": ["已标记回避该公司"],
            "next_action": "skip",
        }

    days_left = _parse_deadline(job.get("deadline", ""))
    deadline_pts = 0
    if days_left is not None:
        if days_left < 0:
            deadline_pts = -20
        elif days_left <= 1:
            deadline_pts = 18
        elif days_left <= 3:
            deadline_pts = 12
        elif days_left <= 7:
            deadline_pts = 6

    legit_pts = 8 if job.get("legitimacy") == "trusted" else 0
    referral_pts = 5 if job.get("referral_code") else 0
    tailored_pts = 15 if _tailored_for_job(client_id, job.get("id", ""), apps) else 0

    applied = any(
        a.get("company") == job.get("company") and a.get("status") in ("Applied", "WrittenTest", "Interview", "Offer")
        for a in apps
    )
    if applied:
        tailored_pts = max(tailored_pts, 20)

    raw = hybrid * 0.55 + deadline_pts + legit_pts + referral_pts + tailored_pts + beh_boost * 100
    readiness = int(min(99, max(5, round(raw))))

    blockers: list[str] = []
    if not resume_md.strip():
        blockers.append("尚无简历，无法评估匹配")
    if days_left is not None and days_left < 0:
        blockers.append("已过截止日")

    next_action = "apply"
    if not tailored_pts and hybrid >= 60:
        next_action = "tailor"
    elif tailored_pts and hybrid >= 50:
        next_action = "export"
    elif hybrid < 45:
        next_action = "review"

    reasons = list(beh_reasons)
    if hybrid >= 70:
        reasons.insert(0, f"匹配度 {hybrid} 分，与简历较契合")
    if days_left is not None and 0 <= days_left <= 3:
        reasons.append(f"截止还剩 {days_left} 天")
    if job.get("referral_code"):
        reasons.append("含内推码，可加速流程")
    if job.get("legitimacy") == "trusted":
        reasons.append("来源可信（官方/校招库）")

    return {
        "readiness_score": readiness,
        "match_score": hybrid,
        "days_to_deadline": days_left,
        "components": {
            "match": hybrid,
            "deadline": deadline_pts,
            "legitimacy": legit_pts,
            "referral": referral_pts,
            "tailored": tailored_pts,
            "behavior": int(beh_boost * 100),
        },
        "reasons": reasons[:5],
        "blockers": blockers,
        "next_action": next_action,
    }


def rank_jobs_with_readiness(
    client_id: str,
    jobs: list[dict],
    resume_md: str,
    *,
    top_k: int = 10,
) -> list[dict]:
    prefs = load_job_preferences(client_id)
    profile = get_behavior_profile(client_id)
    apps = list_applications(client_id)
    ranked = rerank_jobs(resume_md, jobs, prefs=prefs, behavior_profile=profile, top_k=top_k * 2)

    out: list[dict] = []
    for row in ranked:
        job = row["job"]
        rd = compute_readiness(
            job,
            resume_md=resume_md,
            client_id=client_id,
            prefs=prefs,
            apps=apps,
            profile=profile,
        )
        if rd.get("blockers") and "已过截止日" in rd["blockers"]:
            continue
        out.append({**row, "readiness": rd})
    out.sort(key=lambda x: x["readiness"]["readiness_score"], reverse=True)
    return out[:top_k]


def explain_job_rank(job: dict, readiness: dict) -> dict:
    """为什么推荐 / 为什么不推荐。"""
    score = readiness.get("readiness_score", 0)
    if score >= 65:
        headline = "推荐优先投递"
    elif score >= 45:
        headline = "可考虑，建议先改简历"
    else:
        headline = "匹配偏低，谨慎投递"

    return {
        "headline": headline,
        "readiness_score": score,
        "reasons": readiness.get("reasons") or [],
        "blockers": readiness.get("blockers") or [],
        "next_action": readiness.get("next_action", "review"),
    }
