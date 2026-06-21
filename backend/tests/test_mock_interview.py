"""模拟面试回答质量校验。"""
from app.services.mock_interview import assess_answer_quality, _invalid_feedback


def test_xx_placeholder_invalid():
    q = assess_answer_quality("xx")
    assert q["valid"] is False
    assert q["reason"] == "placeholder"
    assert q["score"] <= 15


def test_empty_invalid():
    q = assess_answer_quality("   ")
    assert q["valid"] is False
    assert q["reason"] == "empty"


def test_too_short_invalid():
    q = assess_answer_quality("我觉得还可以")
    assert q["valid"] is False
    assert q["reason"] == "too_short"


def test_valid_star_answer():
    text = (
        "在实习项目中，团队对推荐策略有分歧。我负责梳理双方诉求，"
        "用 A/B 数据对比两套方案，最终采纳点击率提升 12% 的方案并落地。"
    )
    q = assess_answer_quality(text)
    assert q["valid"] is True


def test_invalid_feedback_no_praise():
    fb = _invalid_feedback("placeholder", "测试题")
    assert "优点：暂无" in fb
    assert "敷衍" in fb
    assert "STAR" in fb
