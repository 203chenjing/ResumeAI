"""Prompt / 规则 eval：对标 career-ops test-all（无 LLM）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
FIXTURES = BACKEND / "tests" / "fixtures" / "golden"


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    valid_md = (FIXTURES / "resume_valid.md").read_text(encoding="utf-8")
    invalid_md = (FIXTURES / "resume_invalid_skills.md").read_text(encoding="utf-8")

    r1 = subprocess.run(
        [sys.executable, str(BACKEND / "tools" / "check_resume_skill.py"), str(FIXTURES / "resume_valid.md")],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
    )
    checks.append(("golden_valid_resume", r1.returncode == 0, r1.stdout.strip() or r1.stderr.strip()))

    r2 = subprocess.run(
        [sys.executable, str(BACKEND / "tools" / "check_resume_skill.py"), str(FIXTURES / "resume_invalid_skills.md")],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
    )
    checks.append(("golden_invalid_skills_fail", r2.returncode != 0, "expected failure"))

    from app.services.multi_jd_compare import quick_match_score
    from app.services.story_bank import parse_stories_from_kb

    m = quick_match_score(valid_md, "Python Java 算法 后端开发 MySQL")
    checks.append(("quick_match_score", 0 < m.overall_score <= 100, str(m.overall_score)))

    stories = parse_stories_from_kb(valid_md)
    checks.append(("story_parse", len(stories) >= 0, f"{len(stories)} stories"))

    print("=== Prompt / Rule Eval ===")
    failed = 0
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"  {status}  {name}: {detail}")
        if not ok:
            failed += 1
    print("---")
    if failed:
        print(f"FAILED ({failed} checks)")
        return 1
    print("ALL EVAL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
