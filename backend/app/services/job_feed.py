"""岗位 Feed：聚合爬虫结果，SQLite 存储 + AI  enrichment。"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from urllib.parse import urlparse

from app.crawlers.crawl_config import get_provider_config, load_crawl_config
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.registry import PROVIDERS
from app.services.job_ai_enrichment import enrich_jobs
from app.services.job_cross_verify import cross_verify_jobs
from app.services.job_dedup import is_duplicate, register_fingerprint
from app.services.job_store import MAX_FEED_SIZE, feed_meta, list_jobs, mark_unseen_stale, save_all
from app.services.job_validator import validate_job

__all__ = [
    "list_jobs",
    "feed_meta",
    "add_job",
    "dedupe_feed",
    "organize_feed",
    "crawl_all",
    "crawl_comprehensive",
    "cross_verify_feed",
    "all_enabled_providers",
    "merge_fetched_jobs",
    "QUICK_CRAWL_PROVIDERS",
    "FULL_CRAWL_PROVIDERS",
]

logger = logging.getLogger(__name__)

# 快速刷新：结构化源优先，27 届专项源靠前
QUICK_CRAWL_PROVIDERS = ["qiuzhao_system", "github_joblist", "early_batch", "job_aggregator", "search_discovery"]
FULL_CRAWL_PROVIDERS = QUICK_CRAWL_PROVIDERS + ["company_campus", "campus_patrol", "university_html"]

# 全渠道抓取顺序（含可选 provider）
ALL_PROVIDER_ORDER = [
    "qiuzhao_system",
    "browser_discovery",
    "wechat_discovery",
    "github_joblist",
    "early_batch",
    "job_aggregator",
    "search_discovery",
    "company_campus",
    "campus_patrol",
    "university_html",
    "ats_board",
    "wechat_article",
]


def all_enabled_providers() -> list[str]:
    cfg = load_crawl_config()
    providers = cfg.get("providers") or {}
    out: list[str] = []
    for name in ALL_PROVIDER_ORDER:
        pconf = providers.get(name)
        if not pconf:
            continue
        if pconf.get("enabled", True):
            out.append(name)
    return out


def _is_blocked_domain(url: str, blocked: set[str]) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return any(b in host for b in blocked)
    except Exception:
        return False


def _prepare_job(raw: dict, *, reject_invalid: bool = True) -> dict | None:
    validated = validate_job(raw)
    if reject_invalid and validated.get("validation_status") == "invalid":
        return None
    if not validated.get("id"):
        validated["id"] = uuid.uuid4().hex[:12]
    if not validated.get("crawled_at"):
        validated["crawled_at"] = datetime.now().isoformat()
    return validated


def _enrich_existing(jobs: list[dict]) -> list[dict]:
    out: list[dict] = []
    for j in jobs:
        v = validate_job(j)
        if not v.get("id"):
            v["id"] = uuid.uuid4().hex[:12]
        out.append(v)
    return out


def _merge_core(
    client_id: str,
    new_raw: list[dict],
    existing: list[dict],
    *,
    blocked: set[str],
) -> tuple[list[dict], list[dict], dict]:
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
    cross_merged, cross_stats = cross_verify_jobs(merged)
    final = cross_merged[:MAX_FEED_SIZE]
    stats.update(cross_stats)
    stats["duplicates_removed"] = max(0, len(merged) - len(cross_merged))
    stats["unique"] = len(cross_merged)
    stats["total_in"] = len(merged)
    stats["saved"] = len(final)
    return final, prepared_new, stats


def _sort_jobs_by_quality(jobs: list[dict]) -> list[dict]:
    def _ts(job: dict) -> float:
        raw = job.get("crawled_at") or job.get("updated_at") or ""
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "")).timestamp()
        except Exception:
            return 0.0

    return sorted(
        jobs,
        key=lambda j: (
            0 if j.get("cross_verified") else 1,
            -int(j.get("verification_score") or 0),
            0 if j.get("validation_status") == "ok" else 1,
            0 if j.get("legitimacy") == "trusted" or j.get("source") in {"github_joblist", "ats_board"} else 1,
            -_ts(j),
        ),
    )


async def _merge_and_save(
    client_id: str,
    new_raw: list[dict],
    existing: list[dict],
    *,
    blocked: set[str],
    crawled_sources: set[str] | None = None,
) -> tuple[list[dict], list[dict], dict]:
    final, prepared_new, stats = _merge_core(client_id, new_raw, existing, blocked=blocked)

    if settings_deepseek_available():
        final, ai_stats = await enrich_jobs(final)
        stats["ai_enriched"] = ai_stats.get("enriched", 0)
        stats["ai_tagged"] = ai_stats.get("tagged", 0)
        stats["ai_rejected"] = ai_stats.get("rejected", 0)
        revalidated: list[dict] = []
        for job in final:
            prepared = _prepare_job(job, reject_invalid=False)
            if prepared and prepared.get("validation_status") != "invalid":
                revalidated.append(prepared)
        final = _sort_jobs_by_quality(revalidated)[:MAX_FEED_SIZE]
        stats["validated_ok"] = sum(1 for j in final if j.get("validation_status") == "ok")
        stats["validated_weak"] = sum(1 for j in final if j.get("validation_status") == "weak")
    else:
        stats["ai_enriched"] = 0
        stats["ai_tagged"] = 0
        stats["ai_rejected"] = 0
        final = _sort_jobs_by_quality(final)

    save_all(client_id, final)

    seen_ids = {j.get("id") for j in final if j.get("id")}
    stats["expired_marked"] = 0
    if crawled_sources:
        stats["expired_marked"] = mark_unseen_stale(client_id, seen_ids, sources=crawled_sources)

    return final, prepared_new, stats


def settings_deepseek_available() -> bool:
    from app.config import settings
    return bool(settings.deepseek_api_key)


def add_job(client_id: str, job: dict) -> dict:
    existing = list_jobs(client_id, include_weak=True, include_expired=True)
    prepared = _prepare_job(job, reject_invalid=False)
    if not prepared:
        raise ValueError("岗位信息无效")
    final, _, _ = _merge_core(client_id, [prepared], existing, blocked=set())
    save_all(client_id, final)
    for j in final:
        if j.get("id") == prepared.get("id"):
            return j
    return prepared


def cross_verify_feed(client_id: str) -> dict:
    """对现有岗位库做多渠道交叉确认（不重新爬取）。"""
    existing = list_jobs(client_id, include_weak=True, include_expired=True)
    before = len(existing)
    enriched = _enrich_existing(existing)
    merged, cross_stats = cross_verify_jobs(enriched)
    final = _sort_jobs_by_quality(merged)[:MAX_FEED_SIZE]
    save_all(client_id, final)
    return {
        "before": before,
        "after": len(final),
        "cross_verified": cross_stats.get("cross_verified", 0),
        **cross_stats,
        "jobs": final,
        "meta": feed_meta(client_id),
    }


def dedupe_feed(client_id: str) -> dict:
    existing = list_jobs(client_id, include_weak=True, include_expired=True)
    before = len(existing)
    enriched = _enrich_existing(existing)
    merged, stats = cross_verify_jobs(enriched)
    valid_only = [j for j in merged if j.get("validation_status") != "invalid"]
    final = _sort_jobs_by_quality(valid_only)[:MAX_FEED_SIZE]
    save_all(client_id, final)
    stats["invalid_removed"] = len(merged) - len(valid_only)
    stats["duplicates_removed"] = max(0, before - len(merged))
    stats["ok_count"] = sum(1 for j in final if j.get("validation_status") == "ok")
    stats["weak_count"] = sum(1 for j in final if j.get("validation_status") == "weak")
    return {"before": before, "after": len(final), **stats}


async def organize_feed(client_id: str) -> dict:
    """去重 + 交叉确认 + AI 解析 weak 岗位 + 按质量排序。"""
    existing = list_jobs(client_id, include_weak=True, include_expired=True)
    before = len(existing)
    enriched = _enrich_existing(existing)
    cross_merged, cross_stats = cross_verify_jobs(enriched)
    invalid_count = sum(1 for j in cross_merged if j.get("validation_status") == "invalid")
    candidates = [j for j in cross_merged if j.get("validation_status") != "invalid"]

    ai_stats = {"ai_enriched": 0, "ai_tagged": 0, "ai_rejected": 0}
    if settings_deepseek_available() and candidates:
        candidates, ai_stats = await enrich_jobs(candidates)
        revalidated: list[dict] = []
        for job in candidates:
            prepared = _prepare_job(job, reject_invalid=False)
            if prepared and prepared.get("validation_status") != "invalid":
                revalidated.append(prepared)
        candidates = revalidated
        invalid_count += ai_stats.get("ai_rejected", 0)
        candidates, _ = cross_verify_jobs(candidates)

    final = _sort_jobs_by_quality(candidates)[:MAX_FEED_SIZE]
    save_all(client_id, final)
    ok_count = sum(1 for j in final if j.get("validation_status") == "ok")
    weak_count = sum(1 for j in final if j.get("validation_status") == "weak")
    return {
        "before": before,
        "after": len(final),
        "invalid_removed": invalid_count,
        "duplicates_removed": max(0, before - len(cross_merged)),
        "cross_verified": cross_stats.get("cross_verified", 0),
        "ok_count": ok_count,
        "weak_count": weak_count,
        "actionable": ok_count + weak_count,
        **ai_stats,
        **cross_stats,
    }


async def _append_provider_batch(
    client_id: str,
    batch_raw: list[dict],
    existing: list[dict],
    *,
    blocked: set[str],
    crawled_sources: set[str],
) -> tuple[list[dict], list[dict], dict]:
    """单源抓取后立即入库（不做全库 AI，供增量刷新）。"""
    final, prepared_new, stats = _merge_core(client_id, batch_raw, existing, blocked=blocked)
    final = _sort_jobs_by_quality(final)[:MAX_FEED_SIZE]
    save_all(client_id, final)
    stats["expired_marked"] = 0
    if crawled_sources:
        seen_ids = {j.get("id") for j in final if j.get("id")}
        stats["expired_marked"] = mark_unseen_stale(client_id, seen_ids, sources=crawled_sources)
    return final, prepared_new, stats


async def crawl_all(
    client_id: str,
    providers: list[str] | None = None,
    *,
    incremental_save: bool = False,
    on_progress: Callable[[dict], Awaitable[None] | None] | None = None,
) -> dict:
    cfg = load_crawl_config()
    compliance = cfg.get("compliance") or {}
    blocked = set(compliance.get("blocked_domains") or [])
    if providers:
        names = providers
    else:
        names = QUICK_CRAWL_PROVIDERS

    existing = list_jobs(client_id, include_weak=True, include_expired=True)
    fetched_raw: list[dict] = []
    all_new_jobs: list[dict] = []
    report: list[dict] = []
    crawled_sources: set[str] = set()
    cumulative_new = 0
    fetcher = CrawlFetcher(compliance)

    try:
        for idx, name in enumerate(names, start=1):
            provider = PROVIDERS.get(name)
            pconf = get_provider_config(name)
            if not provider:
                report.append({"provider": name, "status": "skipped", "reason": "unknown provider"})
                if on_progress:
                    await on_progress(
                        {
                            "provider": name,
                            "provider_index": idx,
                            "total": len(existing),
                            "new_count": cumulative_new,
                            "report": list(report),
                        }
                    )
                continue
            if not pconf.get("enabled", True):
                report.append({"provider": name, "status": "skipped", "reason": "disabled in yaml"})
                if on_progress:
                    await on_progress(
                        {
                            "provider": name,
                            "provider_index": idx,
                            "total": len(existing),
                            "new_count": cumulative_new,
                            "report": list(report),
                        }
                    )
                continue

            t0 = datetime.now()
            batch_raw: list[dict] = []
            try:
                fetched = await provider.fetch(pconf, fetcher)
                for job in fetched:
                    row = job.to_dict()
                    batch_raw.append(row)
                    fetched_raw.append(row)
                    crawled_sources.add(job.source)

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

            if incremental_save and batch_raw:
                existing, new_jobs, _ = await _append_provider_batch(
                    client_id,
                    batch_raw,
                    existing,
                    blocked=blocked,
                    crawled_sources=crawled_sources,
                )
                cumulative_new += len(new_jobs)
                all_new_jobs.extend(new_jobs)
            elif incremental_save and on_progress:
                pass

            if on_progress:
                await on_progress(
                    {
                        "provider": name,
                        "provider_index": idx,
                        "total": len(existing),
                        "new_count": cumulative_new,
                        "report": list(report),
                    }
                )
    finally:
        await fetcher.close()

    if incremental_save:
        quality = {
            "validated_ok": sum(1 for j in existing if j.get("validation_status") == "ok"),
            "validated_weak": sum(1 for j in existing if j.get("validation_status") == "weak"),
            "total_in": len(existing),
            "saved": len(existing),
        }
        return {
            "new_jobs": all_new_jobs,
            "new_count": cumulative_new,
            "total": len(existing),
            "report": report,
            "quality": quality,
        }

    merged, new_jobs, quality = await _merge_and_save(
        client_id,
        fetched_raw,
        existing,
        blocked=blocked,
        crawled_sources=crawled_sources or None,
    )

    return {
        "new_jobs": new_jobs,
        "new_count": len(new_jobs),
        "total": len(merged),
        "report": report,
        "quality": quality,
    }


async def merge_fetched_jobs(
    client_id: str,
    fetched_raw: list[dict],
    *,
    crawled_sources: set[str] | None = None,
) -> dict:
    """将已抓取原始岗位合并入库（供浏览器流水线等调用）。"""
    cfg = load_crawl_config()
    blocked = set((cfg.get("compliance") or {}).get("blocked_domains") or [])
    existing = list_jobs(client_id, include_weak=True, include_expired=True)
    merged, new_jobs, quality = await _merge_and_save(
        client_id,
        fetched_raw,
        existing,
        blocked=blocked,
        crawled_sources=crawled_sources,
    )
    return {
        "new_jobs": new_jobs,
        "new_count": len(new_jobs),
        "total": len(merged),
        "quality": quality,
    }


async def crawl_comprehensive(client_id: str) -> dict:
    """全渠道抓取：所有 enabled provider + 交叉确认入库。"""
    return await crawl_all(client_id, all_enabled_providers(), incremental_save=True)
