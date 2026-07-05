from app.services.browser_search import _parse_bing_html, browser_search_sync


def test_parse_bing_html_extracts_results():
    html = """
    <ol id="b_results">
      <li class="b_algo">
        <h2><a href="https://jobs.bytedance.com/campus">字节跳动2027校招</a></h2>
        <div class="b_caption"><p>官方校园招聘</p></div>
      </li>
    </ol>
    """
    hits = _parse_bing_html(html, max_results=5)
    assert len(hits) == 1
    assert "bytedance" in hits[0]["url"]


def test_browser_search_sync_bing(monkeypatch):
    def fake_bing(query, *, max_results, timeout):
        return [{"title": "测试", "url": "https://example.com/campus", "snippet": ""}]

    monkeypatch.setattr("app.services.browser_search._bing_search_httpx", fake_bing)
    hits = browser_search_sync("27届校招", "UA", 5, 10.0)
    assert len(hits) == 1
