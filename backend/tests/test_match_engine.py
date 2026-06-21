"""混合匹配引擎单元测试。"""
from app.services.match_engine import hybrid_match_score, rerank_jobs


def test_hybrid_match_beats_random():
    resume = "熟悉 Python、Java、MySQL、Redis、后端开发、算法实习、大模型 RAG"
    good_jd = "要求 Python Java MySQL Redis 后端 大模型 算法"
    bad_jd = "要求 UI UX Figma 视觉设计 平面设计"
    good, _ = hybrid_match_score(resume, good_jd)
    bad, _ = hybrid_match_score(resume, bad_jd)
    assert good.overall_score > bad.overall_score


def test_rerank_jobs_order():
    resume = "Python 后端 MySQL Redis 实习"
    jobs = [
        {"id": "a", "company": "A", "role": "后端", "jd_text": "Python Java 后端 MySQL"},
        {"id": "b", "company": "B", "role": "设计", "jd_text": "UI UX Figma"},
    ]
    ranked = rerank_jobs(resume, jobs, top_k=2)
    assert ranked[0]["job"]["id"] == "a"
    assert ranked[0]["hybrid_score"] >= ranked[1]["hybrid_score"]


def test_preference_blocklist():
    resume = "Python 开发"
    jd = "Python 工程师"
    prefs = {"company_blocklist": ["某公司"]}
    match, _ = hybrid_match_score(resume, f"某公司 {jd}", prefs=prefs)
    assert match.overall_score <= 10
