"""全渠道刷新 + 交叉确认 + 整理，输出摘要。用法: python scripts/run_full_crawl.py [client_id]"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.crawl_health import record_crawl_run
from app.services.job_feed import (
    all_enabled_providers,
    crawl_comprehensive,
    cross_verify_feed,
    feed_meta,
    list_jobs,
    organize_feed,
)


async def main() -> None:
    client_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    providers = all_enabled_providers()
    before_jobs = list_jobs(client_id, include_weak=True, include_expired=True)
    print(f"=== Full crawl client={client_id} ===")
    print(f"Enabled providers ({len(providers)}): {', '.join(providers)}")
    print(f"Before: {len(before_jobs)} jobs")

    result = await crawl_comprehensive(client_id)
    cross = cross_verify_feed(client_id)
    organize = await organize_feed(client_id)
    after_jobs = list_jobs(client_id, include_weak=True, include_expired=True)

    cohorts = Counter(j.get("graduation_cohort") or "unknown" for j in after_jobs)
    sources = Counter(j.get("source") or "?" for j in after_jobs)
    statuses = Counter(j.get("validation_status") or "?" for j in after_jobs)
    cross_n = sum(1 for j in after_jobs if j.get("cross_verified"))

    summary = {
        "client_id": client_id,
        "providers": providers,
        "before_total": len(before_jobs),
        "new_count": result.get("new_count"),
        "after_total": len(after_jobs),
        "quality": result.get("quality"),
        "cross_verify": cross,
        "cross_verified_jobs": cross_n,
        "organize": organize,
        "cohorts": dict(cohorts),
        "sources": dict(sources),
        "validation_status": dict(statuses),
        "report": result.get("report"),
        "meta": feed_meta(client_id),
    }

    record_crawl_run(
        client_id,
        report=result.get("report") or [],
        new_count=result.get("new_count", 0),
        total=len(after_jobs),
    )

    out = BACKEND / "data" / "full_crawl_report.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nNew: {result.get('new_count')} | After: {len(after_jobs)}")
    print(f"Quality: {result.get('quality')}")
    print(f"Cohorts: {dict(cohorts)}")
    print(f"Sources: {dict(sources)}")
    print(f"Validation: {dict(statuses)}")
    print(f"Cross-verified: {cross_n}")
    print("\nProvider report:")
    for row in result.get("report") or []:
        status = row.get("status")
        prov = row.get("provider")
        fetched = row.get("fetched", "-")
        err = row.get("error", "")
        ms = row.get("duration_ms", "")
        print(f"  {prov}: {status} fetched={fetched} {ms}ms {err}")
    print(f"\nReport saved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
