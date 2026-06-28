"""行为飞轮 + 投递准备度单元测试。"""
from app.services.behavior_signals import behavior_boost_for_job, record_event, update_steer
from app.services.job_readiness import compute_readiness


def test_behavior_boost_wishlist():
    profile = {"steer": {"boost_companies": ["字节跳动"]}, "learned": {}, "dismissed_job_ids": []}
    bonus, reasons = behavior_boost_for_job({"company": "字节跳动", "role": "后端"}, profile)
    assert bonus > 0
    assert reasons


def test_behavior_blocklist():
    profile = {"steer": {"block_companies": ["某外包"]}, "learned": {}, "dismissed_job_ids": []}
    bonus, reasons = behavior_boost_for_job({"company": "某外包公司", "role": "开发"}, profile)
    assert bonus < 0


def test_readiness_trusted_job():
    job = {
        "id": "j1",
        "company": "腾讯",
        "role": "后端开发工程师实习",
        "jd_text": "Python 后端 微服务 北京",
        "legitimacy": "trusted",
        "referral_code": "AB12",
        "deadline": "2099-12-31",
    }
    resume = "Python 后端 微服务 分布式 北京 实习"
    rd = compute_readiness(job, resume_md=resume, client_id="t")
    assert rd["readiness_score"] >= 40
    assert rd["match_score"] >= 30
    assert "next_action" in rd


def test_record_event_and_steer(tmp_path, monkeypatch):
    import app.services.behavior_signals as bs

    monkeypatch.setattr(bs, "DATA_DIR", tmp_path)
    record_event("u1", "tailor_start", job_id="j1", company="阿里", role="开发")
    steer = update_steer("u1", boost_cities=["北京"])
    assert "北京" in steer["boost_cities"]
