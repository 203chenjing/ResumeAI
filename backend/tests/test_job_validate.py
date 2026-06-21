from app.services.job_validator import build_tags, extract_locations, validate_job


def test_extract_locations_from_text():
    locs = extract_locations("岗位地点：北京、上海，可远程")
    assert "北京" in locs
    assert "上海" in locs


def test_validate_ok_with_city_tag():
    job = validate_job(
        {
            "company": "字节跳动",
            "role": "后端开发工程师",
            "jd_text": "负责后端服务开发，工作地点北京",
            "jd_url": "https://jobs.bytedance.com/campus/position/123/detail",
            "city": "北京",
            "channel": "企业校招",
            "source": "company_campus",
        }
    )
    assert job["validation_status"] == "ok"
    assert "来源:北京" in job["tags"]
    assert any(t.startswith("工作地:") for t in job["tags"])


def test_validate_rejects_noise():
    job = validate_job(
        {
            "company": "首页",
            "role": "更多",
            "jd_text": "点击",
            "jd_url": "",
            "source": "university_html",
        }
    )
    assert job["validation_status"] == "invalid"


def test_validate_weak_without_url():
    job = validate_job(
        {
            "company": "蔚来汽车",
            "role": "2026届校招软件工程师",
            "jd_text": "蔚来2026届校招，地点上海，欢迎投递",
            "jd_url": "",
            "city": "上海",
            "source": "job_aggregator",
        }
    )
    assert job["validation_status"] == "weak"
    assert "来源:上海" in job["tags"]


def test_validate_rejects_article_title():
    job = validate_job(
        {
            "company": "清华大学",
            "role": "2026届全国各地选调生信息汇总——学生职业发展指导中心",
            "jd_text": "2026届全国各地选调生信息汇总——学生职业发展指导中心",
            "jd_url": "https://career.tsinghua.edu.cn/example",
            "source": "university_html",
            "city": "北京",
            "tags": ["发布方:清华大学", "校招", "清华"],
        }
    )
    assert job["validation_status"] == "invalid"
    assert job["company"] == "招聘单位待确认"


def test_normalize_university_moves_publisher():
    job = validate_job(
        {
            "company": "北京大学",
            "role": "【美团】2026届产品实习生招聘",
            "jd_text": "【美团】2026届产品实习生招聘",
            "jd_url": "https://scc.pku.edu.cn/job/1",
            "source": "university_html",
            "tags": ["发布方:北京大学", "校招"],
        }
    )
    assert job["company"] == "美团"
    assert job["validation_status"] in ("ok", "weak")


def test_normalize_nowcoder_splits_company_role():
    job = validate_job(
        {
            "company": "大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递",
            "role": "大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递",
            "jd_text": "大众汽车 金融 27届实习 丨 06.15收录 地点： 北京 立即投递",
            "jd_url": "https://www.nowcoder.com/enterprise/32324",
            "source": "job_aggregator",
        }
    )
    assert job["company"] == "大众汽车金融"
    assert job["role"] == "27届实习"
    assert job.get("published_at", "").endswith("-06-15")
    assert job["job_type"] == "实习"


def test_build_tags_dedupes():
    tags = build_tags(
        {
            "city": "杭州",
            "locations": ["杭州", "上海"],
            "channel": "高校就业网",
            "source": "university_html",
            "tags": ["校招", "来源:杭州"],
        }
    )
    assert tags.count("来源:杭州") == 1
    assert "工作地:上海" in tags
