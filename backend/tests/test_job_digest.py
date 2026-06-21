from app.services.job_digest import build_job_digest
from app.services.job_preferences import load_job_preferences, save_job_preferences


def test_job_preferences_roundtrip(tmp_user_memory):
    saved = save_job_preferences(
        "c1",
        {
            "target_roles": ["AI产品实习生"],
            "target_cities": ["上海", "北京"],
            "job_types": ["实习"],
        },
    )
    assert "AI产品实习生" in saved["target_roles"]
    assert "上海" in saved["target_cities"]


async def test_build_job_digest_rule_based(tmp_user_memory):
    prefs = save_job_preferences(
        "digest_test",
        {
            "target_roles": ["AI产品"],
            "target_cities": ["上海"],
            "company_wishlist": ["携程"],
        },
    )
    jobs = [
        {
            "id": "j1",
            "company": "携程计算机技术（上海）有限公司",
            "role": "AI 搜索产品实习生",
            "jd_text": "上海 AI 产品实习",
            "job_type": "实习",
            "locations": ["上海"],
            "validation_status": "ok",
        },
        {
            "id": "j2",
            "company": "某外包公司",
            "role": "运营",
            "jd_text": "成都",
            "job_type": "校招",
            "validation_status": "ok",
        },
    ]

    import app.services.job_digest as jd_mod

    orig_list = jd_mod.list_jobs
    jd_mod.list_jobs = lambda cid, *a, **k: jobs if cid == "digest_test" else []
    try:
        digest = await build_job_digest("digest_test", new_job_ids=["j1"])
    finally:
        jd_mod.list_jobs = orig_list

    assert digest["headline"]
    assert digest["priority_jobs"]
    assert digest["priority_jobs"][0]["job_id"] == "j1"
    assert digest["priority_jobs"][0]["priority"] in ("P0", "P1")
