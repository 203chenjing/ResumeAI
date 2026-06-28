"""混合匹配引擎：BM25 + 技能图谱 + Jaccard，对标 JobRadar rerank 思路（无 embedding 依赖）。"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.models.schemas import GapItem, MatchDimension, MatchResult

STOP = frozenset(
    {
        "负责",
        "要求",
        "岗位",
        "任职",
        "优先",
        "相关",
        "经验",
        "能力",
        "工作",
        "进行",
        "以及",
        "具备",
        "良好",
        "团队",
        "沟通",
        "学习",
    }
)

SKILL_LEXICON = (
    "python",
    "java",
    "c++",
    "go",
    "rust",
    "javascript",
    "typescript",
    "react",
    "vue",
    "sql",
    "mysql",
    "redis",
    "kafka",
    "docker",
    "kubernetes",
    "linux",
    "算法",
    "机器学习",
    "深度学习",
    "nlp",
    "cv",
    "大模型",
    "llm",
    "rag",
    "agent",
    "数据分析",
    "数据挖掘",
    "产品经理",
    "产品实习",
    "用户研究",
    "交互设计",
    "ux",
    "figma",
    "运营",
    "增长",
    "aigc",
    "后端",
    "前端",
    "全栈",
    "测试",
    "运维",
    "安全",
    "嵌入式",
    "硬件",
    "芯片",
    "fpga",
    "verilog",
    "管培",
    "财务",
    "法务",
    "人力资源",
    "市场",
    "品牌",
    "供应链",
)


@dataclass
class HybridBreakdown:
    bm25: float
    skill: float
    jaccard: float
    preference: float
    overall: int


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+#.]{1,}", (text or "").lower())
    return [t for t in raw if t not in STOP and len(t) > 1]


def _bm25_score(query: list[str], doc: list[str], *, k1: float = 1.5, b: float = 0.75) -> float:
    if not query or not doc:
        return 0.0
    doc_freq = Counter(doc)
    dl = len(doc)
    avgdl = max(dl, 12)
    score = 0.0
    for term in set(query):
        tf = doc_freq.get(term, 0)
        if tf == 0:
            continue
        idf = math.log(1 + (1.0 / (0.5 + tf)))
        denom = tf + k1 * (1 - b + b * dl / avgdl)
        score += idf * (tf * (k1 + 1)) / max(denom, 1e-6)
    return score / max(len(set(query)), 1)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _skill_hits(resume_lower: str, jd_lower: str) -> tuple[int, int, list[str]]:
    hits: list[str] = []
    for skill in SKILL_LEXICON:
        if skill in jd_lower and skill in resume_lower:
            hits.append(skill)
    jd_skills = [s for s in SKILL_LEXICON if s in jd_lower]
    if not jd_skills:
        return 0, 0, hits
    return len(hits), len(jd_skills), hits


def _preference_bonus(blob: str, prefs: dict | None) -> float:
    if not prefs:
        return 0.0
    bonus = 0.0
    if any(c in blob for c in prefs.get("company_wishlist") or []):
        bonus += 0.15
    if any(c in blob for c in prefs.get("target_cities") or []):
        bonus += 0.1
    if any(r in blob for r in prefs.get("target_roles") or []):
        bonus += 0.12
    if any(c in blob for c in prefs.get("company_blocklist") or []):
        return -1.0
    return min(bonus, 0.35)


def hybrid_match_score(
    resume_md: str,
    jd_text: str,
    *,
    prefs: dict | None = None,
) -> tuple[MatchResult, HybridBreakdown]:
    resume_lower = (resume_md or "").lower()
    jd_lower = (jd_text or "").lower()
    resume_tokens = tokenize(resume_md)
    jd_tokens = tokenize(jd_text)
    query_tokens = jd_tokens[:60] or tokenize("校招 实习 产品 开发")

    bm25_raw = _bm25_score(query_tokens, resume_tokens)
    bm25_norm = min(1.0, bm25_raw / 4.5)

    skill_hit, skill_total, skill_list = _skill_hits(resume_lower, jd_lower)
    skill_norm = skill_hit / max(skill_total, 1) if skill_total else min(1.0, len(skill_list) / 5)

    jaccard_norm = _jaccard(set(resume_tokens), set(jd_tokens))

    pref = _preference_bonus(f"{jd_text} {resume_md}", prefs)
    if pref < 0:
        overall = 5
        breakdown = HybridBreakdown(0, 0, 0, pref, overall)
        return _build_result(overall, breakdown, query_tokens, resume_lower, skill_list), breakdown

    fused = 0.42 * bm25_norm + 0.33 * skill_norm + 0.25 * jaccard_norm + pref
    overall = int(min(98, max(8, round(fused * 100))))

    breakdown = HybridBreakdown(
        bm25=round(bm25_norm * 100, 1),
        skill=round(skill_norm * 100, 1),
        jaccard=round(jaccard_norm * 100, 1),
        preference=round(pref * 100, 1),
        overall=overall,
    )
    return _build_result(overall, breakdown, query_tokens, resume_lower, skill_list), breakdown


def _build_result(
    overall: int,
    breakdown: HybridBreakdown,
    query_tokens: list[str],
    resume_lower: str,
    skill_hits: list[str],
) -> MatchResult:
    dims = [
        MatchDimension(name="BM25 语义", score=int(breakdown.bm25), max=100),
        MatchDimension(name="技能图谱", score=int(breakdown.skill), max=100),
        MatchDimension(name="关键词 Jaccard", score=int(breakdown.jaccard), max=100),
        MatchDimension(name="偏好加权", score=int(max(0, breakdown.preference)), max=100),
        MatchDimension(name="综合匹配", score=overall, max=100),
    ]

    gaps: list[GapItem] = []
    seen: set[str] = set()
    for kw in query_tokens[:12]:
        if kw in seen:
            continue
        seen.add(kw)
        if kw in resume_lower:
            gaps.append(GapItem(requirement=kw, status="match", detail="简历已覆盖"))
        else:
            gaps.append(GapItem(requirement=kw, status="missing", detail="建议补充或改写"))

    for sk in skill_hits[:4]:
        gaps.append(GapItem(requirement=sk, status="match", detail="技能命中"))

    return MatchResult(overall_score=overall, dimensions=dims, gap_analysis=gaps[:12])


def rerank_jobs(
    resume_md: str,
    jobs: list[dict],
    *,
    prefs: dict | None = None,
    behavior_profile: dict | None = None,
    top_k: int = 20,
) -> list[dict]:
    """按混合分对岗位重排，返回带 score_breakdown 的行。可选行为飞轮加权。"""
    from app.services.behavior_signals import behavior_boost_for_job

    scored: list[dict] = []
    for job in jobs:
        jd_text = job.get("jd_text", "") or job.get("role", "")
        match, breakdown = hybrid_match_score(resume_md, jd_text, prefs=prefs)
        beh, beh_reasons = behavior_boost_for_job(job, behavior_profile)
        hybrid = breakdown.overall
        if beh < -0.3:
            hybrid = max(5, hybrid - 40)
        else:
            hybrid = int(min(99, hybrid + round(beh * 100)))
        scored.append(
            {
                "job": job,
                "match": match,
                "score_breakdown": {
                    "bm25": breakdown.bm25,
                    "skill": breakdown.skill,
                    "jaccard": breakdown.jaccard,
                    "preference": breakdown.preference,
                    "behavior": round(beh * 100, 1),
                },
                "hybrid_score": hybrid,
                "behavior_reasons": beh_reasons,
            }
        )
    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return scored[:top_k]
