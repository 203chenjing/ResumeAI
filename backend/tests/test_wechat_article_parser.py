from app.services.wechat_article_parser import parse_wechat_article_html


def test_parse_wechat_article_html_js_content():
    html = """
    <html><head>
      <meta property="og:title" content="腾讯27届校招启动" />
      <meta property="og:description" content="面向2027届毕业生" />
    </head><body>
      <span id="js_name">腾讯招聘</span>
      <em id="publish_time">2026-03-01</em>
      <div id="js_content">
        <p>2027届校园招聘</p>
        <a href="https://join.qq.com/post.html">投递入口</a>
      </div>
    </body></html>
    """
    art = parse_wechat_article_html(html, "https://mp.weixin.qq.com/s/abc")
    assert art.title == "腾讯27届校招启动"
    assert art.account_name == "腾讯招聘"
    assert "join.qq.com" in art.apply_links[0]
    assert "2027届" in art.content_text
