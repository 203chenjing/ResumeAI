"""届别回填与统计。"""
from __future__ import annotations

from app.services.job_store import list_jobs, save_all
from app.services.job_validator import validate_job


def backfill_graduation_cohort(client_id: str) -> dict:
    """对现有岗位库重新校验并写入 graduation_cohort。"""
    jobs = list_jobs(client_id, include_weak=True, include_expired=True)
    updated: list[dict] = []
    stats = {"total": len(jobs), "cohort_27": 0, "cohort_26": 0, "unknown": 0}
    for job in jobs:
        validated = validate_job(job)
        validated["id"] = job.get("id") or validated.get("id")
        validated["crawled_at"] = job.get("crawled_at") or validated.get("crawled_at")
        validated["ai_summary"] = job.get("ai_summary") or validated.get("ai_summary")
        validated["ai_tags"] = job.get("ai_tags") or validated.get("ai_tags")
        cohort = validated.get("graduation_cohort") or ""
        if cohort == "27届":
            stats["cohort_27"] += 1
        elif cohort == "26届":
            stats["cohort_26"] += 1
        else:
            stats["unknown"] += 1
        updated.append(validated)
    save_all(client_id, updated)
    return stats
