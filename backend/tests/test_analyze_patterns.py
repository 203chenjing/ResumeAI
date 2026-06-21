"""拒信模式分析测试。"""
from app.services.analyze_patterns import analyze_patterns
from app.services.application_store import create_application, _save, _load


def test_analyze_patterns_empty():
    cid = "test_patterns_empty"
    _save(cid, [])
    result = analyze_patterns(cid)
    assert result["total"] == 0
    assert result["recommendations"]


def test_analyze_patterns_with_data():
    cid = "test_patterns_data"
    _save(cid, [])
    create_application(cid, {"company": "A", "role": "dev", "status": "Rejected", "match_score": 45, "channel": "官网"})
    create_application(cid, {"company": "B", "role": "dev", "status": "Applied", "match_score": 75, "channel": "内推"})
    result = analyze_patterns(cid)
    assert result["total"] >= 2
    assert "by_channel" in result
