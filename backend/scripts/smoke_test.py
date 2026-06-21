"""API 冒烟测试：无需启动 uvicorn、无需 LLM API Key。"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


def run() -> int:
    client = TestClient(app)
    failures: list[str] = []

    def assert_check(name: str, ok: bool, detail: str = ""):
        if ok:
            print(f"  OK  {name}")
        else:
            print(f"  FAIL {name}: {detail}")
            failures.append(name)

    print("=== ResumeAI Smoke Test ===")

    r = client.get("/health")
    assert_check("health", r.status_code == 200 and r.json().get("status") == "ok", r.text)

    r = client.get("/api/knowledge-base/template")
    tpl = (r.json().get("data") or {}).get("template", "")
    assert_check("knowledge_template", r.status_code == 200 and len(tpl) > 50, r.text[:200])

    r = client.get("/api/session/bad_id_smoke")
    assert_check("session_404", r.status_code == 404)

    r = client.put(
        "/api/user-memory",
        json={"client_id": "smoke_test", "knowledge_base_md": "smoke", "notes": "x"},
    )
    assert_check("user_memory_put", r.status_code == 200 and r.json().get("success"), r.text[:200])

    r = client.get("/api/user-memory/smoke_test")
    kb = (r.json().get("data") or {}).get("knowledge_base_md", "")
    assert_check("user_memory_get", r.status_code == 200 and kb == "smoke", r.text[:200])

    golden = BACKEND / "tests" / "fixtures" / "golden" / "resume_valid.md"
    if golden.exists():
        sys.path.insert(0, str(BACKEND / "tools"))
        from check_resume_skill import check as skill_check  # noqa: E402

        issues = skill_check(golden)
        assert_check("golden_resume_valid", len(issues) == 0, "; ".join(issues))

    r = client.get("/api/jobs/feed/smoke_test")
    assert_check("jobs_feed", r.status_code == 200 and r.json().get("success"), r.text[:200])

    r = client.get("/api/jobs/crawl-config")
    assert_check("crawl_config", r.status_code == 200 and r.json().get("success"), r.text[:200])

    import os

    if os.getenv("RUN_LIVE_CRAWL") == "1":
        r = client.post("/api/jobs/crawl", json={"client_id": "smoke_test", "providers": ["company_campus"]})
        d = r.json()
        assert_check(
            "jobs_crawl",
            r.status_code == 200 and d.get("success") and "report" in (d.get("data") or {}),
            r.text[:300],
        )
    else:
        print("  SKIP jobs_crawl (set RUN_LIVE_CRAWL=1 for live Playwright crawl)")

    r = client.get("/api/reminders/smoke_test")
    assert_check("reminders", r.status_code == 200, r.text[:200])

    r = client.get("/api/insights/patterns/smoke_test")
    assert_check("insights_patterns", r.status_code == 200, r.text[:200])

    r = client.get("/api/user-profile/smoke_test")
    assert_check("user_profile", r.status_code == 200, r.text[:200])

    r = client.get("/api/applications/smoke_test")
    assert_check("applications", r.status_code == 200, r.text[:200])

    print("---")
    if failures:
        print(f"FAILED ({len(failures)}): {', '.join(failures)}")
        return 1
    print("ALL SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
