import sys
from pathlib import Path

# tools/ 下的 check 函数
TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from check_resume_skill import check  # noqa: E402


def test_valid_resume_passes(golden_dir):
    issues = check(golden_dir / "resume_valid.md")
    assert issues == []


def test_invalid_resume_fails(golden_dir):
    issues = check(golden_dir / "resume_invalid_skills.md")
    assert len(issues) >= 1
