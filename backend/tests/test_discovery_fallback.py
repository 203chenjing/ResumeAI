from app.services.discovery_fallback import (
    looks_like_campus_url,
    make_fallback_job_from_page,
    make_fallback_jobs_from_search_hits,
)


def test_fallback_from_campus_url():
    job = make_fallback_job_from_page(
        title="字节跳动校园招聘",
        url="https://jobs.bytedance.com/campus",
        text="2027届 提前批",
        cohort="27届",
        source="browser_discovery",
        channel="浏览器检索",
    )
    assert job is not None
    assert "bytedance" in job.jd_url


def test_fallback_skips_random_blog():
    job = make_fallback_job_from_page(
        title="Random blog",
        url="https://example.com/blog/post",
        text="hello world",
        cohort="27届",
        source="browser_discovery",
        channel="浏览器检索",
    )
    assert job is None


def test_fallback_from_search_hits():
    hits = [
        {"title": "腾讯27届校招", "url": "https://join.qq.com/post.html", "snippet": "校园招聘"},
        {"title": "无关", "url": "https://example.com/news", "snippet": "news"},
    ]
    jobs = make_fallback_jobs_from_search_hits(
        hits, cohort="27届", source="search_discovery", channel="AI搜索发现"
    )
    assert len(jobs) == 1
    assert looks_like_campus_url(jobs[0].jd_url)
