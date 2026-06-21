"""飞书多维表格映射与秋招过滤。"""
from app.services.feishu_bitable import (
    extract_cell_text,
    matches_job_type_filter,
    record_to_job,
    resolve_field_map,
)


def test_extract_cell_text_url():
    assert extract_cell_text({"link": "https://jobs.example.com", "text": "投递"}) == "投递 https://jobs.example.com"


def test_record_to_job_keeps_qiuzhao_only():
    ok = record_to_job(
        {
            "record_id": "rec001",
            "fields": {
                "公司": "字节跳动",
                "岗位": "AI产品实习生",
                "类型": "秋招",
                "工作地点": "北京",
                "投递链接": {"link": "https://jobs.bytedance.com/1", "text": "网申"},
            },
        },
        source_id="test",
        channel="飞书秋招表",
        include_types=["秋招"],
    )
    assert ok is not None
    assert ok["company"] == "字节跳动"
    assert ok["job_type"] == "秋招"
    assert ok["jd_url"] == "https://jobs.bytedance.com/1"


def test_record_to_job_skips_internship():
    skipped = record_to_job(
        {
            "record_id": "rec002",
            "fields": {
                "公司": "腾讯",
                "岗位": "产品实习",
                "类型": "实习",
                "投递链接": "https://join.qq.com",
            },
        },
        source_id="test",
        channel="飞书秋招表",
        include_types=["秋招"],
        exclude_types=["实习", "春招"],
    )
    assert skipped is None


def test_record_to_job_keeps_qiuzhao_in_role_text():
    ok = record_to_job(
        {
            "record_id": "rec003",
            "fields": {
                "公司": "美团",
                "岗位": "26届秋招-产品经理",
                "工作地点": "上海",
            },
        },
        source_id="test",
        channel="飞书秋招表",
        include_types=["秋招"],
    )
    assert ok is not None
    assert ok["role"].startswith("26届秋招")


def test_resolve_field_map_aliases():
    mapped = resolve_field_map(
        {"企业名称": "阿里", "招聘职位": "算法工程师", "网申链接": "https://a.com"},
        {"company": ["企业名称"], "role": ["招聘职位"], "jd_url": ["网申链接"]},
    )
    assert mapped["company"] == "阿里"
    assert mapped["role"] == "算法工程师"
    assert mapped["jd_url"] == "https://a.com"


def test_matches_job_type_filter():
    assert matches_job_type_filter({"job_type": "秋招", "role": "产品"}, include_types=["秋招"])
    assert not matches_job_type_filter({"job_type": "实习", "role": "产品实习"}, include_types=["秋招"])
