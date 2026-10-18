"""定稿预检：把校验结果翻译成带动作的问题清单。"""
from app.services.preflight import build_issues, blocking_issues

METRICS = {
    "char_count": 3050,
    "estimated_pages": 1.33,
    "capacity_pct": 100,
    "experience_items": 12,
    "experience_limit": 5,
    "skill_items": 4,
    "skill_limit": 4,
}

VALIDATION_FAIL = {
    "skill_passed": False,
    "skill_issues": ["某段实习经历有 12 条编号项，应 ≤ 5"],
    "page_count": 2,
    "page_passed": False,
    "layout_issues": ["PDF 为 2 页，必须为 1 页"],
}

VALIDATION_OK = {
    "skill_passed": True,
    "skill_issues": [],
    "page_count": 1,
    "page_passed": True,
    "layout_issues": [],
}


def test_page_issue_offers_compress_action():
    issues = build_issues(VALIDATION_FAIL, METRICS)
    codes = {i["code"]: i for i in issues}
    assert "page_count" in codes
    assert codes["page_count"]["action"] == "compress"
    assert codes["page_count"]["blocking"] is True


def test_skill_issue_gets_actionable_hint():
    issues = build_issues(VALIDATION_FAIL, METRICS)
    skill = next(i for i in issues if i["code"] == "skill")
    assert "子要点" in skill["hint"]
    assert skill["action"] == "edit"


def test_bottom_gap_is_warning_not_blocker():
    validation = {**VALIDATION_OK, "page_passed": False, "layout_issues": ["页底留白约 30mm，偏多"]}
    issues = build_issues(validation, METRICS)
    gap = next(i for i in issues if i["code"] == "bottom_gap")
    assert gap["blocking"] is False
    assert not blocking_issues(validation, METRICS)


def test_force_keeps_only_hard_failures():
    """用户选择「仍然导出」时，页数与格式问题不再阻断。"""
    assert blocking_issues(VALIDATION_FAIL, METRICS, force=True) == []

    render_fail = {
        "skill_passed": True,
        "skill_issues": [],
        "page_count": 0,
        "page_passed": False,
        "layout_issues": ["PDF 渲染组件不可用：请先执行 `python -m playwright install chromium` 后重试"],
    }
    hard = blocking_issues(render_fail, METRICS, force=True)
    assert [i["code"] for i in hard] == ["render_unavailable"]


def test_ok_validation_has_no_blocking_issues():
    issues = build_issues(VALIDATION_OK, METRICS)
    assert not [i for i in issues if i["blocking"]]
