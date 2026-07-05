"""多渠道岗位交叉确认：同源合并、来源佐证、可信度评分。"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from app.services.job_dedup import canonical_url, normalize_company, normalize_role

SOURCE_TRUST: dict[str, int] = {
    "browser_discovery": 28,
    "wechat_discovery": 26,
    "company_campus": 30,
    "github_joblist": 26,
    "early_batch": 28,
    "campus_patrol": 25,
    "ats_board": 24,
    "job_aggregator": 20,
    "university_html": 18,
    "search_discovery": 16,
    "wechat_article": 14,
}

LIST_PAGE_MARKERS = (
    "/schedule",
    "/recruitmentfairlist",
    "/recruitmentinfolist",
    "/anony/xxfb",
    "ncss.cn/",
    "bjbys.net.cn/",
)


def _cluster_key(job: dict) -> str:
    url = canonical_url(job.get("jd_url", ""))
    is_list = url and any(m in url for m in LIST_PAGE_MARKERS) and "/detail" not in url
    if url and not is_list:
        return f"url:{url}"

    company = normalize_company(job.get("company", ""))
    role = normalize_role(job.get("role", ""))[:40]
    cohort = (job.get("graduation_cohort") or "").strip()
    job_type = (job.get("job_type") or "").strip()
    if company and role:
        return f"fp:{company}|{role}|{cohort}|{job_type}"
    return f"id:{job.get('id', '')}"


def _attestation(job: dict) -> dict:
    return {
        "source": job.get("source") or "",
        "channel": job.get("channel") or "",
        "jd_url": job.get("jd_url") or "",
        "legitimacy": job.get("legitimacy") or "",
        "crawled_at": job.get("crawled_at") or "",
        "source_site": job.get("source_site") or "",
        "graduation_cohort": job.get("graduation_cohort") or "",
        "cohort_confidence": job.get("cohort_confidence") or "",
    }


def _primary_score(job: dict) -> tuple:
    status_rank = 0 if job.get("validation_status") == "ok" else 1
    trust = SOURCE_TRUST.get(job.get("source") or "", 10)
    has_url = 0 if job.get("jd_url") else 1
    ts = 0.0
    raw = job.get("published_at") or job.get("crawled_at") or ""
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "")).timestamp()
    except Exception:
        pass
    verified = 0 if job.get("cross_verified") else 1
    return (status_rank, verified, -trust, has_url, -ts)


def _merge_tags(primary: dict, others: list[dict]) -> list[str]:
    tags: list[str] = []
    for job in [primary, *others]:
        for t in job.get("tags") or []:
            t = str(t).strip()
            if t and t not in tags:
                tags.append(t)
    if len({j.get("source") for j in [primary, *others] if j.get("source")}) >= 2:
        if "多渠道确认" not in tags:
            tags.insert(0, "多渠道确认")
    return tags[:14]


def _pick_cohort(primary: dict, group: list[dict]) -> tuple[str, str]:
    for job in sorted(group, key=_primary_score):
        if job.get("cohort_confidence") == "explicit" and job.get("graduation_cohort"):
            return job["graduation_cohort"], "explicit"
    for job in group:
        if job.get("graduation_cohort"):
            return job["graduation_cohort"], job.get("cohort_confidence") or "inferred"
    return primary.get("graduation_cohort") or "", primary.get("cohort_confidence") or "unknown"


def _merge_cluster(group: list[dict]) -> dict:
    if len(group) == 1:
        job = dict(group[0])
        src = job.get("source") or ""
        job["source_attestations"] = [_attestation(job)]
        job["verification_source_count"] = 1 if src else 0
        job["verification_score"] = min(100, SOURCE_TRUST.get(src, 10) + 10)
        job["cross_verified"] = False
        return job

    primary = sorted(group, key=_primary_score)[0]
    out = dict(primary)
    seen_sources: dict[str, dict] = {}
    for job in group:
        src = job.get("source") or "unknown"
        prev = seen_sources.get(src)
        if not prev or _primary_score(job) < _primary_score(prev):
            seen_sources[src] = job

    attestations = [_attestation(j) for j in seen_sources.values()]
    source_count = len(seen_sources)
    cross_verified = source_count >= 2
    score = min(
        100,
        sum(SOURCE_TRUST.get(s, 10) for s in seen_sources) + (15 if cross_verified else 0),
    )

    cohort, cohort_conf = _pick_cohort(primary, group)
    out["source_attestations"] = attestations
    out["verification_source_count"] = source_count
    out["verification_score"] = score
    out["cross_verified"] = cross_verified
    out["graduation_cohort"] = cohort
    out["cohort_confidence"] = cohort_conf
    out["tags"] = _merge_tags(primary, [j for j in group if j is not primary])

    if cross_verified:
        out["legitimacy"] = "trusted"
        if out.get("validation_status") == "weak" and out.get("jd_url"):
            out["validation_status"] = "ok"
            out["validation_issues"] = [
                i for i in (out.get("validation_issues") or []) if i not in ("无官方链接", "未识别工作地")
            ]

    # 合并更完整的 JD 文本
    jd_parts = [j.get("jd_text") for j in group if j.get("jd_text")]
    if jd_parts:
        out["jd_text"] = max(jd_parts, key=len)[:2000]

    alt_urls = [a["jd_url"] for a in attestations if a.get("jd_url") and a["jd_url"] != out.get("jd_url")]
    if alt_urls:
        out["alternate_jd_urls"] = alt_urls[:5]

    return out


def cross_verify_jobs(jobs: list[dict]) -> tuple[list[dict], dict]:
    """按公司/岗位/URL 聚类，合并多渠道记录并计算交叉确认分。"""
    clusters: dict[str, list[dict]] = defaultdict(list)
    for job in jobs:
        if job.get("validation_status") == "invalid":
            continue
        clusters[_cluster_key(job)].append(job)

    merged: list[dict] = []
    cross_verified = 0
    total_attestations = 0
    for group in clusters.values():
        item = _merge_cluster(group)
        merged.append(item)
        if item.get("cross_verified"):
            cross_verified += 1
        total_attestations += len(item.get("source_attestations") or [])

    merged.sort(
        key=lambda j: (
            0 if j.get("cross_verified") else 1,
            -int(j.get("verification_score") or 0),
            0 if j.get("validation_status") == "ok" else 1,
        )
    )

    stats = {
        "clusters": len(clusters),
        "merged_total": len(merged),
        "cross_verified": cross_verified,
        "total_attestations": total_attestations,
        "input_total": len(jobs),
    }
    return merged, stats


def attestations_summary(job: dict) -> str:
    items = job.get("source_attestations") or []
    if not items:
        return job.get("channel") or job.get("source") or ""
    labels = []
    for a in items:
        label = a.get("channel") or a.get("source") or "来源"
        if label not in labels:
            labels.append(label)
    return "、".join(labels[:4])
