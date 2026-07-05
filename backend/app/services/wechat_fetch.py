"""抓取并解析公开 mp.weixin.qq.com 文章。"""
from __future__ import annotations

import logging

import httpx

from app.services.wechat_article_parser import WechatArticle, parse_wechat_article_html

logger = logging.getLogger(__name__)

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def fetch_wechat_article(url: str, *, timeout: float = 25.0) -> WechatArticle:
    """httpx 抓取 + 结构化解析（优先移动端 UA，参考高星项目做法）。"""
    last_err: Exception | None = None
    for ua in (MOBILE_UA, DESKTOP_UA):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": ua}) as http:
                resp = await http.get(url)
                resp.raise_for_status()
                if "链接已过期" in resp.text or "该内容已被发布者删除" in resp.text:
                    logger.warning("wechat article expired url=%s", url[:80])
                    return parse_wechat_article_html(resp.text, str(resp.url))
                article = parse_wechat_article_html(resp.text, str(resp.url))
                if len(article.content_text) >= 60:
                    return article
        except Exception as e:
            last_err = e
            logger.debug("fetch_wechat_article ua retry url=%s: %s", url[:60], e)
    if last_err:
        logger.warning("fetch_wechat_article failed url=%s: %s", url[:80], last_err)
    return WechatArticle(url=url, title="公众号文章", content_text="")
