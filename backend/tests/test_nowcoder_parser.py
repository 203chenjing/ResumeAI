from app.crawlers.parsers import parse_nowcoder_card_text, parse_nowcoder_enterprise_text, split_position_titles
from app.services.job_validator import normalize_nowcoder_job, validate_job


def test_parse_nowcoder_card_text():
    parsed = parse_nowcoder_card_text("大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递")
    assert parsed["company"] == "大众汽车金融"
    assert parsed["role"] == "27届实习"
    assert parsed["location"] == "北京"
    assert parsed["published"] == "06.15"


def test_parse_nowcoder_card_text_multi_city():
    parsed = parse_nowcoder_card_text("星图测控 27提前批 丨 06.14收录 地点： 合肥、西安 立即投递")
    assert parsed["company"] == "星图测控"
    assert parsed["role"] == "27提前批"
    assert "合肥" in parsed["location"]


def test_parse_nowcoder_enterprise_text():
    text = """
    招聘批次：27届实习
    网申时间：2026/06/05 ~ 2026/07/05
    招聘城市：北京
    招聘岗位：后端开发、运维、财务审计
    """
    detail = parse_nowcoder_enterprise_text(text)
    assert detail["batch"] == "27届实习"
    assert "2026/06/05" in detail["deadline"]
    assert detail["city"] == "北京"
    assert "后端开发" in detail["positions"]


def test_split_position_titles():
    assert split_position_titles("后端开发、运维、财务审计") == ["后端开发", "运维", "财务审计"]


def test_normalize_nowcoder_job_fixes_legacy_row():
    raw = {
        "company": "大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递",
        "role": "大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递",
        "jd_text": "大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递",
        "jd_url": "https://www.nowcoder.com/enterprise/32324",
        "source": "job_aggregator",
        "channel": "牛客校招日程",
        "tags": ["聚合", "job_aggregator"],
    }
    fixed = validate_job(raw)
    assert fixed["company"] == "大众汽车金融"
    assert fixed["role"] == "27届实习"
    assert "job_aggregator" not in fixed["tags"]
