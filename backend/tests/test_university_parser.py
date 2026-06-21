"""高校就业网解析：不把学校名当用人单位。"""
from app.crawlers.parsers import parse_text_lines, _is_career_article_title


def test_skips_career_center_articles():
    text = "\n".join(
        [
            "2026届全国各地选调生信息汇总——学生职业发展指导中心",
            "2026年暑期清华学子地域行实习实践活动",
            "地址：北京市海淀区清华大学",
            "【字节跳动】2026校园招聘 后端工程师",
        ]
    )
    jobs = parse_text_lines(
        text,
        source_id="tsinghua",
        source_name="清华大学",
        channel="高校就业网",
        base_url="https://career.example.edu.cn/",
        source_type="university_html",
        tags=["校招", "清华"],
    )
    assert len(jobs) == 1
    assert jobs[0].company == "字节跳动"
    assert "发布方:清华大学" in jobs[0].tags


def test_career_article_detector():
    assert _is_career_article_title("2026届选调生信息汇总")
    assert _is_career_article_title("地址：北京市海淀区清华大学")
