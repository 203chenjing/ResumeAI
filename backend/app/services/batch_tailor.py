"""批量 tailoring 预览：多岗位匹配 + 差距 + 行动建议（轻量，默认零 token）。"""
from __future__ import annotations

from app.services.job_feed import list_jobs
from app.services.job_preferences import load_job_preferences
from app.services.job_readiness import compute_readiness, rank_jobs_with_readiness
from app.services.master_resume import get_active_master
from app.services.user_memory import load_memory


def _resume(client_id: str, resume_md: str = "") -> str:
    if resume_md.strip():
        return resume_md
    master = get_active_master(client_id)
    if master and master.get("markdown"):
        return master["markdown"]
    return load_memory(client_id).get("knowledge_base_md", "") or ""


def batch_tailor_preview(
    client_id: str,
    job_ids: list[str],
    *,
    resume_md: str = "",
) -> list[dict]:
    resume = _resume(client_id, resume_md)
    if not resume.strip():
        raise ValueError("需要母版简历或知识库才能批量评估")

    id_set = set(job_ids[:8])
    jobs = [j for j in list_jobs(client_id, include_weak=False) if j.get("id") in id_set]
    prefs = load_job_preferences(client_id)

    rows: list[dict] = []
    for job in jobs:
        rd = compute_readiness(job, resume_md=resume, client_id=client_id, prefs=prefs)
        gaps = []
        from app.services.match_engine import hybrid_match_score

        match, _ = hybrid_match_score(resume, job.get("jd_text", "") or job.get("role", ""), prefs=prefs)
        for g in (match.gap_analysis or [])[:5]:
            if getattr(g, "status", None) == "missing" or (isinstance(g, dict) and g.get("status") == "missing"):
                req = getattr(g, "requirement", None) or g.get("requirement", "")
                if req:
                    gaps.append(req)

        action = "为此岗位改简历" if rd.get("next_action") == "tailor" else "查看匹配详情"
        rows.append(
            {
                "job_id": job.get("id"),
                "company": job.get("company"),
                "role": job.get("role"),
                "readiness_score": rd.get("readiness_score"),
                "match_score": rd.get("match_score"),
                "top_gaps": gaps[:4],
                "reasons": rd.get("reasons", [])[:3],
                "action_label": action,
                "jd_url": job.get("jd_url"),
            }
        )

    rows.sort(key=lambda r: r.get("readiness_score", 0), reverse=True)
    return rows


def suggest_batch_job_ids(client_id: str, resume_md: str = "", *, limit: int = 5) -> list[str]:
    resume = _resume(client_id, resume_md)
    jobs = list_jobs(client_id, include_weak=False)
    ranked = rank_jobs_with_readiness(client_id, jobs, resume, top_k=limit)
    return [r["job"]["id"] for r in ranked if r.get("job", {}).get("id")]
