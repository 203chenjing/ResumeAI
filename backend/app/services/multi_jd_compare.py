"""多 JD 对比：混合匹配引擎 + 投递决策。"""
from __future__ import annotations

import re

from app.services.application_advisor import application_decision
from app.models.schemas import GapItem, JDAnalysis, MatchDimension, MatchResult
from app.services.match_engine import hybrid_match_score


def _extract_keywords(text: str) -> set[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+#.]{1,}", text.lower())
    stop = {"负责", "要求", "岗位", "任职", "优先", "相关", "经验", "能力", "工作", "进行", "以及"}
    return {t for t in tokens if t not in stop and len(t) > 1}


def quick_match_score(resume_md: str, jd_text: str, *, prefs: dict | None = None) -> MatchResult:
    """混合匹配评分（BM25 + 技能 + Jaccard），批量对比与 digest 共用。"""
    match, _ = hybrid_match_score(resume_md, jd_text, prefs=prefs)
    return match


def compare_jobs(
    resume_md: str,
    jobs: list[dict],
    *,
    prefs: dict | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for job in jobs:
        jd_text = job.get("jd_text", "")
        match, breakdown = hybrid_match_score(resume_md, jd_text, prefs=prefs)
        pseudo_jd = JDAnalysis(
            role=job.get("role", ""),
            company=job.get("company", ""),
            archetype="",
            core_requirements=[],
            preferred_requirements=[],
            keywords=list(_extract_keywords(jd_text))[:15],
            soft_skills=[],
            industry_terms=[],
            legitimacy_score=85,
            legitimacy_flags=[],
            ranking={},
        )
        decision = application_decision(match, pseudo_jd)
        rows.append(
            {
                "job_id": job.get("id", ""),
                "company": job.get("company", ""),
                "role": job.get("role", ""),
                "deadline": job.get("deadline", ""),
                "source": job.get("source", ""),
                "match": match.model_dump(),
                "score_breakdown": {
                    "bm25": breakdown.bm25,
                    "skill": breakdown.skill,
                    "jaccard": breakdown.jaccard,
                    "preference": breakdown.preference,
                },
                "decision": decision,
            }
        )
    rows.sort(key=lambda r: r["decision"]["match_score"], reverse=True)
    return rows
