"""多 JD 对比单元测试。"""
from app.services.multi_jd_compare import compare_jobs, quick_match_score


def test_quick_match_score_range():
    resume = "熟悉 Python、Java、算法、MySQL、Redis、分布式系统开发经验"
    jd = "要求 Python Java 算法 MySQL Redis 消息队列 后端开发"
    match = quick_match_score(resume, jd)
    assert 40 <= match.overall_score <= 100
    assert len(match.dimensions) == 5


def test_compare_jobs_sorted():
    resume = "Python 后端开发 MySQL Redis 实习项目"
    jobs = [
        {"id": "a", "company": "A", "role": "后端", "jd_text": "Python Java 后端"},
        {"id": "b", "company": "B", "role": "设计", "jd_text": "UI UX Figma 视觉设计"},
    ]
    rows = compare_jobs(resume, jobs)
    assert len(rows) == 2
    assert rows[0]["decision"]["match_score"] >= rows[1]["decision"]["match_score"]
