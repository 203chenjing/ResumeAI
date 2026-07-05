from app.services.wechat_discovery import (
    build_sogou_queries,
    build_wechat_queries,
    filter_wechat_article_urls,
    _canonical_wechat_url,
)


def test_build_wechat_queries():
    qs = build_wechat_queries({"target_cohort": "27届"})
    assert len(qs) >= 2
    assert any("mp.weixin.qq.com" in q or "公众号" in q for q in qs)


def test_build_sogou_queries_includes_accounts():
    qs = build_sogou_queries({"target_cohort": "27届", "subscribed_accounts": ["校招汇"]})
    assert any("校招汇" in q for q in qs)
    assert all("site:mp.weixin.qq.com" not in q for q in qs)


def test_canonical_wechat_url():
    assert _canonical_wechat_url("https://mp.weixin.qq.com/s/abc123?chksm=xxx") == "https://mp.weixin.qq.com/s/abc123"
    assert _canonical_wechat_url("https://www.zhipin.com/job/1") is None


def test_filter_wechat_article_urls():
    rows = [
        {"title": "27届提前批", "url": "https://mp.weixin.qq.com/s/abc"},
        {"title": "boss", "url": "https://www.zhipin.com/job/1"},
        {"title": "dup", "url": "https://mp.weixin.qq.com/s/abc?x=1"},
    ]
    out = filter_wechat_article_urls(rows, max_urls=5)
    assert len(out) == 1
    assert out[0]["url"] == "https://mp.weixin.qq.com/s/abc"
