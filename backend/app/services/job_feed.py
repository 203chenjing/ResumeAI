"""岗位 Feed 缓存：聚合爬虫结果（读取 crawl_sources.yml）。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.crawlers.crawl_config import get_provider_config, load_crawl_config
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.registry import PROVIDERS
from app.services.job_dedup import deduplicate_jobs, is_duplicate, register_fingerprint
from app.services.job_validator import validate_job

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "job_feed"
MAX_FEED_SIZE = 500


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


def _save(client_id: str, jobs: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path(client_id).write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_blocked_domain(url: str, blocked: set[str]) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return any(b in host for b in blocked)
    except Exception:
        return False


def _prepare_job(raw: dict, *, reject_invalid: bool = True) -> dict | None:
    """校验 + 打标签（含来源地）。"""
    validated = validate_job(raw)
    if reject_invalid and validated.get("validation_status") == "invalid":
        return None
    if not validated.get("id"):
        validated["id"] = uuid.uuid4().hex[:12]
    if not validated.get("crawled_at"):
        validated["crawled_at"] = datetime.now().isoformat()
    return validated


def _enrich_existing(jobs: list[dict]) -> list[dict]:
    """对历史数据补全校验与标签（不丢弃 invalid）。"""
    out: list[dict] = []
    for j in jobs:
        v = validate_job(j)
        if not v.get("id"):
            v["id"] = uuid.uuid4().hex[:12]
        out.append(v)
    return out


def _merge_and_save(
    client_id: str,
    new_raw: list[dict],
    existing: list[dict],
    *,
    blocked: set[str],
) -> tuple[list[dict], list[dict], dict]:
    """校验新岗位 → 与存量合并 → 全量去重 → 保存。"""
    stats = {
        "validated_ok": 0,
        "validated_weak": 0,
        "rejected": 0,
        "dup_skipped_new": 0,
    }

    seen: set[str] = set()
    for j in _enrich_existing(existing):
        register_fingerprint(j, seen)

    prepared_new: list[dict] = []
    for raw in new_raw:
        url = raw.get("jd_url", "")
        if url and _is_blocked_domain(url, blocked):
            stats["rejected"] += 1
            continue
        job = _prepare_job(raw)
        if not job:
            stats["rejected"] += 1
            continue
        if job.get("validation_status") == "weak":
            stats["validated_weak"] += 1
        else:
            stats["validated_ok"] += 1
        if is_duplicate(job, seen):
            stats["dup_skipped_new"] += 1
            continue
        register_fingerprint(job, seen)
        prepared_new.append(job)

    merged = prepared_new + _enrich_existing(existing)
    deduped, dedup_stats = deduplicate_jobs(merged)
    final = deduped[:MAX_FEED_SIZE]
    _save(client_id, final)
    stats.update(dedup_stats)
    stats["saved"] = len(final)
    return final, prepared_new, stats


def list_jobs(
    client_id: str,
    source: str | None = None,
    *,
    job_type: str | None = None,
    work_city: str | None = None,
    include_invalid: bool = False,
    include_weak: bool = True,
) -> list[dict]:
    jobs = _enrich_existing(_load(client_id))
    if source:
        jobs = [j for j in jobs if j.get("source") == source]
    if job_type:
        jobs = [j for j in jobs if j.get("job_type") == job_type]
    if work_city:
        jobs = [
            j
            for j in jobs
            if work_city in (j.get("locations") or [])
            or work_city in (j.get("location") or "")
            or any(work_city in t for t in (j.get("tags") or []) if t.startswith("工作地:"))
        ]
    if not include_invalid:
        jobs = [j for j in jobs if j.get("validation_status") != "invalid"]
    if not include_weak:
        jobs = [j for j in jobs if j.get("validation_status") != "weak"]
    jobs.sort(
        key=lambda j: j.get("published_at") or j.get("crawled_at") or "",
        reverse=True,
    )
    return jobs


def feed_meta(client_id: str) -> dict:
    jobs = list_jobs(client_id, include_weak=True)
    types: dict[str, int] = {}
    sources: dict[str, int] = {}
    cities: dict[str, int] = {}
    for j in jobs:
        jt = j.get("job_type") or "校招"
        types[jt] = types.get(jt, 0) + 1
        src = j.get("source") or "unknown"
        sources[src] = sources.get(src, 0) + 1
        for loc in j.get("locations") or []:
            cities[loc] = cities.get(loc, 0) + 1
    crawled = [j.get("crawled_at") for j in jobs if j.get("crawled_at")]
    return {
        "total": len(jobs),
        "job_types": types,
        "sources": sources,
        "work_cities": cities,
        "last_crawled_at": max(crawled) if crawled else "",
    }


def add_job(client_id: str, job: dict) -> dict:
    existing = _load(client_id)
    prepared = _prepare_job(job, reject_invalid=False)
    if not prepared:
        raise ValueError("岗位信息无效")
    merged, prepared_new, _ = _merge_and_save(client_id, [prepared], existing, blocked=set())
    for j in merged:
        if j.get("id") == prepared.get("id"):
            return j
    return prepared


def dedupe_feed(client_id: str) -> dict:
    """对已有 Feed 全量校验、打标签、去重，并剔除 invalid。"""
    existing = _load(client_id)
    enriched = _enrich_existing(existing)
    deduped, stats = deduplicate_jobs(enriched)
    valid_only = [j for j in deduped if j.get("validation_status") != "invalid"]
    final = valid_only[:MAX_FEED_SIZE]
    _save(client_id, final)
    stats["invalid_removed"] = len(deduped) - len(valid_only)
    return {"before": len(existing), "after": len(final), **stats}


async def crawl_all(
    client_id: str,
    providers: list[str] | None = None,
) -> dict:
    """执行爬虫批次，返回 new_jobs + crawl_report。"""
    cfg = load_crawl_config()
    compliance = cfg.get("compliance") or {}
    blocked = set(compliance.get("blocked_domains") or [])
    names = providers or [n for n, p in (cfg.get("providers") or {}).items() if p.get("enabled", True)]

    existing = _load(client_id)
    fetched_raw: list[dict] = []
    report: list[dict] = []
    fetcher = CrawlFetcher(compliance)

    try:
        for name in names:
            provider = PROVIDERS.get(name)
            pconf = get_provider_config(name)
            if not provider:
                report.append({"provider": name, "status": "skipped", "reason": "unknown provider"})
                continue
            if not pconf.get("enabled", True):
                report.append({"provider": name, "status": "skipped", "reason": "disabled in yaml"})
                continue

            t0 = datetime.now()
            try:
                fetched = await provider.fetch(pconf, fetcher)
                for job in fetched:
                    fetched_raw.append(job.to_dict())

                report.append(
                    {
                        "provider": name,
                        "status": "ok",
                        "fetched": len(fetched),
                        "duration_ms": int((datetime.now() - t0).total_seconds() * 1000),
                    }
                )
            except Exception as e:
                logger.exception("crawl provider %s failed", name)
                report.append(
                    {
                        "provider": name,
                        "status": "error",
                        "error": str(e),
                        "duration_ms": int((datetime.now() - t0).total_seconds() * 1000),
                    }
                )
    finally:
        await fetcher.close()

    merged, new_jobs, quality = _merge_and_save(client_id, fetched_raw, existing, blocked=blocked)

    return {
        "new_jobs": new_jobs,
        "new_count": len(new_jobs),
        "total": len(merged),
        "report": report,
        "quality": quality,
    }
