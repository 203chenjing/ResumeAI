from app.crawlers.github_joblist import _parse_markdown_table, is_category_heading
from app.services.job_graduation import (
    enrich_graduation,
    extract_graduation_classes,
    get_graduation_classes,
    matches_graduation_filter,
)
from app.services.job_validator import validate_job


def test_extract_graduation_classes():
    assert extract_graduation_classes("拼多多 27届实习") == ["27"]
    assert extract_graduation_classes("字节 26届秋招") == ["26"]
    assert extract_graduation_classes("华为 26/27届校招") == ["26", "27"]
    assert extract_graduation_classes("后端开发工程师") == []


def test_matches_graduation_filter_27():
    j27 = enrich_graduation({"company": "拼多多", "role": "27届实习", "jd_text": "", "tags": []})
    j26 = enrich_graduation({"company": "阿里", "role": "26届春招", "jd_text": "", "tags": []})
    j_blank = {"company": "腾讯", "role": "校招正式批", "jd_text": "", "tags": []}

    assert matches_graduation_filter(j27, "27") is True
    assert matches_graduation_filter(j26, "27") is False
    assert matches_graduation_filter(j_blank, "27", include_unlabeled=False) is False
    assert matches_graduation_filter(j_blank, "27", include_unlabeled=True) is True


def test_enrich_graduation_tags():
    out = enrich_graduation({"company": "拼多多", "role": "大模型算法实习生", "jd_text": "27届实习", "tags": []})
    assert get_graduation_classes(out) == ["27"]
    assert "届别:27届" in out["tags"]


BATCH_MD = """
## <h3 id="18">拼多多</h3>
27届实习
|NO.|工作岗位|详细内容|
|---|---|---|
|1|大模型算法实习生|[点击查看](https://careers.pddglobalhr.com/campus/intern/1)|
|2|服务端研发实习生|[点击查看](https://careers.pddglobalhr.com/campus/intern/2)|

## 游戏
|NO.|工作岗位|详细内容|
|---|---|---|
|1|Java开发|[点击查看](https://example.com/1)|
"""


def test_github_parser_batch_and_skip_category():
    jobs = _parse_markdown_table(BATCH_MD, {"id": "0voice", "tags": ["GitHub"]})
    assert len(jobs) == 2
    assert all(j.company == "拼多多" for j in jobs)
    assert all(get_graduation_classes(validate_job(j.to_dict())) == ["27"] for j in jobs)
    assert not any(j.company == "游戏" for j in jobs)


def test_is_category_heading():
    assert is_category_heading("游戏")
    assert is_category_heading("后端岗位")
    assert not is_category_heading("拼多多")
    assert not is_category_heading("阿里巴巴")
