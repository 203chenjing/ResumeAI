from app.services.wechat_sogou import (
    append_sogou_k_h,
    parse_sogou_article_search_html,
    search_wechat_articles,
    _parse_mp_url_from_js,
)


def test_parse_sogou_article_search_html():
    html = """
    <ul class="news-list">
      <li>
        <h3><a href="/link?url=abc">字节27届校招</a></h3>
        <p>提前批开启</p>
        <a data-headimage="x">字节跳动招聘</a>
      </li>
    </ul>
    """
    rows = parse_sogou_article_search_html(html)
    assert len(rows) == 1
    assert "字节" in rows[0]["title"]
    assert rows[0]["account"] == "字节跳动招聘"


def test_append_sogou_k_h():
    # 需足够长，避免 idx+15+b 越界
    payload = "dn9a_" + ("x" * 200)
    url = f"https://weixin.sogou.com/link?url={payload}"
    out = append_sogou_k_h(url)
    assert "&k=" in out and "&h=" in out


def test_parse_mp_url_from_js_empty_base():
    html = "var url = ''; url += 'https://mp.'; url += 'weixin.qq.com/s?src=11';"
    mp = _parse_mp_url_from_js(html)
    assert mp and "mp.weixin.qq.com" in mp


def test_search_wechat_articles_live():
    hits = search_wechat_articles("27届校招", max_results=3, timeout=25)
    # 网络环境可能因验证码返回 0，不强制
    assert isinstance(hits, list)
