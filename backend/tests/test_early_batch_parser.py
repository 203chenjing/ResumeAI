from app.crawlers.parsers import parse_early_batch_html


def test_parse_early_batch_html_extracts_links():
    html = """
    <html><body>
    <a href="https://join.qq.com/post.html">腾讯</a>
    <a href="https://jobs.bytedance.com/campus">字节跳动</a>
    <span class="cr-co" data-go="https://campus.jd.com/"><span class="cr-co-name">京东</span></span>
    <a href="javascript:void(0)">登录</a>
    </body></html>
    """
    jobs = parse_early_batch_html(
        html,
        source_id="test",
        source_name="test",
        channel="27届提前批",
        base_url="https://example.com",
        max_items=10,
    )
    assert len(jobs) >= 3
    companies = {j.company for j in jobs}
    assert "腾讯" in companies
    assert "京东" in companies
    assert all(j.source == "early_batch" for j in jobs)
    assert jobs[0].job_type == "提前批"
