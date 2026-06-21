"""投递决策：对标 career-ops oferta 分档 + Resume-Matcher 匹配分。"""
from __future__ import annotations

from app.models.schemas import JDAnalysis, MatchResult


def application_decision(
    match: MatchResult | None,
    jd: JDAnalysis | None = None,
) -> dict:
    score = match.overall_score if match else 0
    legitimacy = jd.legitimacy_score if jd else 100

    if legitimacy < 60:
        level = "risk"
        label = "JD 真实性风险较高，请谨慎投递"
        recommend = False
    elif score >= 80:
        level = "strong"
        label = "强烈建议投递"
        recommend = True
    elif score >= 60:
        level = "moderate"
        label = "可以投递，建议先补强差距项"
        recommend = True
    else:
        level = "weak"
        label = "匹配度偏低，不建议海投（可强制继续）"
        recommend = False

    top_gaps = []
    if match:
        top_gaps = [
            g.requirement
            for g in match.gap_analysis
            if g.status in ("partial", "missing")
        ][:5]

    return {
        "match_score": score,
        "legitimacy_score": legitimacy,
        "level": level,
        "label": label,
        "recommend_apply": recommend,
        "top_gaps": top_gaps,
    }
