from app.services.browser_discovery import build_queries, filter_official_urls


def test_build_queries_defaults_to_27():
    qs = build_queries({"target_cohort": "27届"})
    assert len(qs) >= 2
    assert any("27" in q or "2027" in q for q in qs)


def test_filter_official_urls_blocks_boss():
    results = [
        {"title": "字节27届校招", "url": "https://jobs.bytedance.com/campus"},
        {"title": "BOSS", "url": "https://www.zhipin.com/job/1"},
    ]
    out = filter_official_urls(results, max_urls=5)
    assert len(out) == 1
    assert "bytedance" in out[0]["url"]
