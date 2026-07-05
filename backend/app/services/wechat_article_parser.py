"""微信公众号文章解析 — 借鉴 wechat-download-api / WechatSogou get_article_detail。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

CAMPUS_LINK_HINTS = ("campus", "jobs.", "join.", "talent.", "careers.", "zhaopin.", "recruit", "mokahr.com/campus")
BLOCKED_LINKS = ("zhipin.com", "liepin.com", "51job.com")


@dataclass
class WechatArticle:
    url: str
    title: str = ""
    account_name: str = ""
    author: str = ""
    publish_time: str = ""
    description: str = ""
    content_text: str = ""
    content_html: str = ""
    apply_links: list[str] = field(default_factory=list)


def _meta(soup: BeautifulSoup, prop: str) -> str:
    el = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return (el.get("content") or "").strip() if el else ""


def _extract_apply_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href.startswith("http"):
            continue
        host = urlparse(href).netloc.lower()
        if any(b in host for b in BLOCKED_LINKS):
            continue
        if any(h in href.lower() for h in CAMPUS_LINK_HINTS):
            key = href.split("?")[0]
            if key not in seen:
                seen.add(key)
                links.append(href)
    return links[:12]


def parse_wechat_article_html(html: str, url: str = "") -> WechatArticle:
    soup = BeautifulSoup(html or "", "lxml")
    title = _meta(soup, "og:title")
    if not title:
        t = soup.find("title")
        title = (t.get_text(strip=True) if t else "").strip()

    account = ""
    nick = soup.select_one("#js_name") or soup.select_one(".rich_media_meta_nickname")
    if nick:
        account = nick.get_text(strip=True)
    if not account:
        account = _meta(soup, "og:article:author")

    author_el = soup.select_one("#js_author_name") or soup.select_one(".rich_media_meta_text")
    author = author_el.get_text(strip=True) if author_el else ""

    publish_el = soup.select_one("#publish_time") or soup.select_one("#meta_content_hide_info")
    publish_time = publish_el.get_text(strip=True) if publish_el else ""

    description = _meta(soup, "og:description")

    content = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    content_text = content.get_text("\n", strip=True) if content else ""
    content_html = str(content) if content else ""

    if not content_text and description:
        content_text = description
    if not content_text:
        content_text = re.sub(r"<[^>]+>", " ", html or "")
        content_text = re.sub(r"\s+", " ", content_text).strip()

    apply_links = _extract_apply_links(soup, url)

    return WechatArticle(
        url=url,
        title=title,
        account_name=account,
        author=author,
        publish_time=publish_time,
        description=description,
        content_text=content_text[:12000],
        content_html=content_html[:20000],
        apply_links=apply_links,
    )
