"""公众号链接提取测试。"""
from app.crawlers.wechat_article import extract_wechat_urls


def test_extract_wechat_urls():
    html = """
    <a href="https://mp.weixin.qq.com/s/abc123">校招</a>
    <p>详见 https://mp.weixin.qq.com/s/xyz789?scene=1</p>
    """
    urls = extract_wechat_urls(html)
    assert len(urls) >= 2
