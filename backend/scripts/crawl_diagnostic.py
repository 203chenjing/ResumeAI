"""爬虫分 provider 诊断脚本。用法: python scripts/crawl_diagnostic.py"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.crawlers.crawl_config import get_provider_config, load_crawl_config
from app.crawlers.fetcher import CrawlFetcher
from app.crawlers.registry import PROVIDERS
from app.services.job_store import DB_PATH, list_jobs, save_all
from app.services.job_validator import validate_job

CLIENT = "crawl_diagnostic"
PROVIDERS_ORDER = ["job_aggregator", "company_campus", "university_html", "wechat_article"]


async def test_provider(name: str, fetcher: CrawlFetcher) -> dict:
    provider = PROVIDERS.get(name)
    pconf = get_provider_config(name)
    if not provider or not pconf.get("enabled", True):
        return {"provider": name, "status": "skipped", "reason": "disabled or missing"}

    t0 = asyncio.get_event_loop().time()
    try:
        jobs = await provider.fetch(pconf, fetcher)
        raw = [j.to_dict() for j in jobs]
        validated = [validate_job(j) for j in raw]
        ok = sum(1 for j in validated if j.get("validation_status") == "ok")
        weak = sum(1 for j in validated if j.get("validation_status") == "weak")
        invalid = sum(1 for j in validated if j.get("validation_status") == "invalid")
        companies = Counter(j.get("company", "?")[:30] for j in validated if j.get("validation_status") != "invalid")
        samples = []
        for j in validated:
            if j.get("validation_status") == "ok" and len(samples) < 3:
                samples.append(
                    {
                        "company": j.get("company"),
                        "role": j.get("role"),
                        "job_type": j.get("job_type"),
                        "locations": j.get("locations"),
                        "jd_url": (j.get("jd_url") or "")[:80],
                        "channel": j.get("channel"),
                    }
                )
        return {
            "provider": name,
            "status": "ok",
            "fetched": len(raw),
            "ok": ok,
            "weak": weak,
            "invalid": invalid,
            "actionable_rate": round((ok + weak) / max(len(raw), 1) * 100, 1),
            "ok_rate": round(ok / max(len(raw), 1) * 100, 1),
            "duration_s": round(asyncio.get_event_loop().time() - t0, 1),
            "top_companies": companies.most_common(5),
            "samples": samples,
        }
    except Exception as e:
        return {
            "provider": name,
            "status": "error",
            "error": str(e),
            "duration_s": round(asyncio.get_event_loop().time() - t0, 1),
        }


async def test_nowcoder_only(fetcher: CrawlFetcher) -> dict:
    pconf = get_provider_config("job_aggregator")
    sources = [s for s in (pconf.get("sources") or []) if "nowcoder" in (s.get("id") or "")]
    results = []
    from app.crawlers.parsers import parse_source_page

    for src in sources:
        t0 = asyncio.get_event_loop().time()
        try:
            jobs = await parse_source_page(fetcher, src, "job_aggregator")
            raw = [j.to_dict() for j in jobs]
            validated = [validate_job(j) for j in raw]
            ok = sum(1 for j in validated if j.get("validation_status") == "ok")
            with_url = sum(1 for j in validated if j.get("jd_url"))
            with_positions = sum(1 for j in validated if "招聘岗位" in (j.get("jd_text") or ""))
            results.append(
                {
                    "source_id": src.get("id"),
                    "name": src.get("name"),
                    "fetched": len(raw),
                    "ok": ok,
                    "with_url": with_url,
                    "with_positions_field": with_positions,
                    "duration_s": round(asyncio.get_event_loop().time() - t0, 1),
                    "sample": [
                        {
                            "company": j.get("company"),
                            "role": j.get("role"),
                            "deadline": j.get("deadline"),
                            "locations": j.get("locations"),
                        }
                        for j in validated
                        if j.get("validation_status") == "ok"
                    ][:2],
                }
            )
        except Exception as e:
            results.append({"source_id": src.get("id"), "status": "error", "error": str(e)})
    return {"nowcoder_sources": results}


async def main():
    cfg = load_crawl_config()
    compliance = cfg.get("compliance") or {}
    fetcher = CrawlFetcher(compliance)
    report = {"providers": [], "nowcoder_detail": None, "full_pipeline": None}

    print("=== ResumeAI Crawler Diagnostic ===\n")
    try:
        for name in PROVIDERS_ORDER:
            if name not in PROVIDERS:
                continue
            print(f"Testing {name}...", flush=True)
            r = await test_provider(name, fetcher)
            report["providers"].append(r)
            if r.get("status") == "ok":
                print(
                    f"  {name}: fetched={r['fetched']} ok={r['ok']} weak={r['weak']} "
                    f"invalid={r['invalid']} ok_rate={r['ok_rate']}% ({r['duration_s']}s)"
                )
            else:
                print(f"  {name}: {r.get('status')} - {r.get('error') or r.get('reason')}")

        print("\nTesting nowcoder sources individually...", flush=True)
        report["nowcoder_detail"] = await test_nowcoder_only(fetcher)
        for ns in report["nowcoder_detail"]["nowcoder_sources"]:
            print(f"  {ns.get('source_id')}: {json.dumps(ns, ensure_ascii=False)[:200]}")

        # Full pipeline (no AI if no key)
        print("\nRunning full crawl_all pipeline...", flush=True)
        from app.services.job_feed import crawl_all

        save_all(CLIENT, [])
        result = await crawl_all(CLIENT)
        jobs = list_jobs(CLIENT)
        statuses = Counter(j.get("validation_status") for j in jobs)
        sources = Counter(j.get("source") for j in jobs)
        report["full_pipeline"] = {
            "new_count": result.get("new_count"),
            "total": result.get("total"),
            "quality": result.get("quality"),
            "report": result.get("report"),
            "status_breakdown": dict(statuses),
            "source_breakdown": dict(sources),
            "sample_ok": [
                {"company": j.get("company"), "role": j.get("role"), "source": j.get("source")}
                for j in jobs
                if j.get("validation_status") == "ok"
            ][:8],
            "sample_weak": [
                {"company": j.get("company"), "role": j.get("role"), "issues": j.get("validation_issues")}
                for j in jobs
                if j.get("validation_status") == "weak"
            ][:5],
        }
        print(f"  Pipeline: new={result['new_count']} total={result['total']}")
        print(f"  Quality: {result.get('quality')}")
        print(f"  Status: {dict(statuses)}")
        print(f"  Sources: {dict(sources)}")

    finally:
        await fetcher.close()

    out = BACKEND / "data" / "crawl_diagnostic_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport saved: {out}")
    print(f"SQLite DB: {DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
