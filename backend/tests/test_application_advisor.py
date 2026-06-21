"""投递决策分单元测试。"""
from app.models.schemas import GapItem, JDAnalysis, MatchDimension, MatchResult
from app.services.application_advisor import application_decision


def test_strong_recommend():
    match = MatchResult(
        overall_score=85,
        dimensions=[MatchDimension(name="技能", score=80, max=100)],
        gap_analysis=[],
    )
    d = application_decision(match, JDAnalysis(legitimacy_score=90))
    assert d["level"] == "strong"
    assert d["recommend_apply"] is True


def test_weak_not_recommend():
    match = MatchResult(overall_score=45, dimensions=[], gap_analysis=[])
    d = application_decision(match)
    assert d["level"] == "weak"
    assert d["recommend_apply"] is False


def test_risk_jd():
    match = MatchResult(overall_score=90, dimensions=[], gap_analysis=[])
    jd = JDAnalysis(legitimacy_score=40)
    d = application_decision(match, jd)
    assert d["level"] == "risk"
    assert d["recommend_apply"] is False


def test_top_gaps():
    match = MatchResult(
        overall_score=70,
        dimensions=[],
        gap_analysis=[
            GapItem(requirement="Python", status="missing", detail=""),
            GapItem(requirement="SQL", status="partial", detail=""),
        ],
    )
    d = application_decision(match)
    assert "Python" in d["top_gaps"]
