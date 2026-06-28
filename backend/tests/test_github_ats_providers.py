from app.crawlers.ats_board import _campus_only, _china_only, _greenhouse, _lever
from app.crawlers.base import JobPosting
from app.crawlers.github_joblist import (
    _extract_referral,
    _parse_json_listings,
    _parse_markdown_table,
)
from app.services.job_validator import is_china_location, validate_job


MD = """
# 实习岗位

| Company | Role | Location | Application |
| --- | --- | --- | --- |
| [字节跳动](https://bytedance.com) | 后端开发实习 | 北京、上海 | [Apply](https://jobs.bytedance.com/123) 内推码: ABCD1234 |
| 腾讯 | 算法工程师 | 深圳 | [投递](https://careers.tencent.com/9) |
| OldCorp | 已结束岗位 🔒 | 杭州 | [link](https://x.com) |
"""


def test_parse_markdown_table_basic():
    jobs = _parse_markdown_table(MD, {"id": "t", "tags": ["实习", "GitHub"]})
    assert len(jobs) == 2  # closed row dropped
    first = jobs[0]
    assert first.company == "字节跳动"
    assert first.role == "后端开发实习"
    assert first.jd_url == "https://jobs.bytedance.com/123"
    assert first.referral_code == "ABCD1234"
    assert "北京" in first.locations
    assert first.legitimacy == "trusted"


def test_extract_referral():
    assert _extract_referral("欢迎内推码：XY12AB 加速") == "XY12AB"
    assert _extract_referral("no code here") == ""
    # 中文内推码常为纯字母，需能识别
    assert _extract_referral("内推码：DBQMSUOJ") == "DBQMSUOJ"
    assert _extract_referral("内推码 NTAciAS") == "NTAciAS"


HEADING_MD = """
## 大厂岗

## <h3 id="5">阿里巴巴</h3>

|NO.|工作岗位|详细内容|
|---|---|---|
|1|AI Infra工程师|[点击查看](https://campus-talent.alibaba.com/position/1)|
|2|算法工程师|[点击查看](https://campus-talent.alibaba.com/position/2)|

### 蚂蚁集团

|NO.|工作岗位|详细内容|
|---|---|---|
|1|后端开发|[点击查看](https://talent.antgroup.com/3)|
"""


def test_parse_markdown_heading_aware():
    jobs = _parse_markdown_table(HEADING_MD, {"id": "0voice"})
    assert len(jobs) == 3
    ali = [j for j in jobs if j.company == "阿里巴巴"]
    assert len(ali) == 2
    assert ali[0].role == "AI Infra工程师"
    assert ali[0].jd_url == "https://campus-talent.alibaba.com/position/1"
    ant = [j for j in jobs if j.company == "蚂蚁集团"]
    assert len(ant) == 1
    # 分类标题不应被当成公司
    assert all(j.company not in ("大厂岗",) for j in jobs)


def test_is_china_location():
    assert is_china_location("北京")
    assert is_china_location("Shanghai, China")
    assert is_china_location("全国")
    assert not is_china_location("San Francisco, CA")
    assert not is_china_location("Singapore")


def test_ats_china_filter():
    jobs = [
        JobPosting(id="1", company="MS", role="SWE Intern", source="ats_board", jd_text="", location="Beijing, China"),
        JobPosting(id="2", company="MS", role="SWE Intern", source="ats_board", jd_text="", location="Seattle, WA"),
    ]
    out = _china_only(jobs)
    assert len(out) == 1
    assert out[0].location == "Beijing, China"


def test_china_only_markdown_filter():
    md = """
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Acme | SWE | San Francisco | [a](https://a.co) |
| 北京公司 | 后端 | 北京 | [b](https://b.co) |
"""
    jobs = _parse_markdown_table(md, {"id": "t"}, china_only=True)
    assert len(jobs) == 1
    assert jobs[0].company == "北京公司"


def test_parse_json_listings():
    payload = """[
        {"company_name": "Acme", "title": "SWE Intern", "url": "https://a.co/1", "locations": ["Beijing"], "active": true},
        {"company": "Closed", "title": "Gone", "url": "https://b.co", "active": false}
    ]"""
    jobs = _parse_json_listings(payload, {"id": "j"})
    assert len(jobs) == 1
    assert jobs[0].company == "Acme"
    assert jobs[0].location == "Beijing"


def test_greenhouse_and_campus_filter():
    rows = [
        {"id": 1, "title": "Software Engineer Intern", "absolute_url": "https://gh/1", "location": {"name": "SF"}},
        {"id": 2, "title": "Senior Staff Engineer", "absolute_url": "https://gh/2", "location": {"name": "NY"}},
    ]
    jobs = _greenhouse({"name": "Stripe"}, rows)
    assert len(jobs) == 2
    campus = _campus_only(jobs)
    assert len(campus) == 1
    assert campus[0].role == "Software Engineer Intern"


def test_lever_parse():
    rows = [{"id": "x", "text": "New Grad SWE", "hostedUrl": "https://lever/x", "categories": {"location": "Remote"}}]
    jobs = _lever({"name": "Airtable"}, rows)
    assert jobs[0].company == "Airtable"
    assert jobs[0].jd_url == "https://lever/x"


def test_trusted_source_validates_ok_despite_short_jd():
    job = JobPosting(
        id="1",
        company="字节跳动",
        role="后端开发实习",
        source="github_joblist",
        jd_text="字节跳动 后端开发实习 北京",
        jd_url="https://jobs.bytedance.com/123",
        legitimacy="trusted",
    ).to_dict()
    result = validate_job(job)
    assert result["validation_status"] == "ok"
    assert result["legitimacy"] == "trusted"
