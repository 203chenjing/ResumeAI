from app.services.job_dedup import canonical_url, deduplicate_jobs, fingerprint, normalize_company, normalize_role


def test_canonical_url_strips_wechat_query():
    u = "https://mp.weixin.qq.com/s/abc?chksm=xxx"
    assert canonical_url(u) == "https://mp.weixin.qq.com/s/abc"


def test_fingerprint_same_url():
    a = {"company": "A", "role": "工程师", "jd_url": "https://jobs.bytedance.com/campus/position/1/detail"}
    b = {"company": "B", "role": "其他", "jd_url": "https://jobs.bytedance.com/campus/position/1/detail"}
    assert fingerprint(a) == fingerprint(b)


def test_dedup_by_company_role():
    jobs = [
        {
            "company": "蔚来汽车科技有限公司",
            "role": "软件工程师 2026届",
            "jd_text": "校招",
            "city": "上海",
            "jd_url": "",
        },
        {
            "company": "蔚来汽车",
            "role": "软件工程师2026届",
            "jd_text": "校招 duplicate",
            "city": "上海",
            "jd_url": "",
        },
    ]
    out, stats = deduplicate_jobs(jobs)
    assert len(out) == 1
    assert stats["duplicates_removed"] == 1


def test_normalize_company():
    assert normalize_company("蔚来汽车科技有限公司") == normalize_company("蔚来汽车")
