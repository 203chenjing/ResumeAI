from app.services.job_cross_verify import cross_verify_jobs


def test_cross_verify_merges_same_company_role():
    jobs = [
        {
            "id": "1",
            "company": "字节跳动",
            "role": "27届实习",
            "source": "company_campus",
            "channel": "企业校招",
            "jd_url": "https://jobs.bytedance.com/campus/1",
            "validation_status": "ok",
            "graduation_cohort": "27届",
        },
        {
            "id": "2",
            "company": "字节跳动科技有限公司",
            "role": "27届实习",
            "source": "github_joblist",
            "channel": "GitHub校招仓库",
            "jd_url": "https://jobs.bytedance.com/campus/1",
            "validation_status": "ok",
            "graduation_cohort": "27届",
        },
    ]
    merged, stats = cross_verify_jobs(jobs)
    assert len(merged) == 1
    assert merged[0]["cross_verified"] is True
    assert merged[0]["verification_source_count"] == 2
    assert len(merged[0]["source_attestations"]) == 2
    assert stats["cross_verified"] == 1


def test_cross_verify_keeps_distinct_companies():
    jobs = [
        {
            "id": "1",
            "company": "腾讯",
            "role": "27届校招",
            "source": "early_batch",
            "jd_url": "https://join.qq.com/1",
            "validation_status": "ok",
        },
        {
            "id": "2",
            "company": "阿里巴巴",
            "role": "27届校招",
            "source": "early_batch",
            "jd_url": "https://talent.alibaba.com/1",
            "validation_status": "ok",
        },
    ]
    merged, stats = cross_verify_jobs(jobs)
    assert len(merged) == 2
    assert stats["cross_verified"] == 0
