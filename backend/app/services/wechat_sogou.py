"""搜狗微信搜索 — 借鉴 WechatSogou (6k★) 思路，无第三方依赖。

合规边界：仅使用公开搜狗微信搜索 + 公开 mp.weixin.qq.com 文章页，不登录微信后台。
"""
from __future__ import annotations

import logging
import math
import random
import re
import time
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOGOU_WEIXIN = "https://weixin.sogou.com/weixin"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MP_WECHAT_RE = re.compile(r"https?://mp\.weixin\.qq\.com/s(?:/[A-Za-z0-9_\-]+|\?[^\s\"'<>]+)", re.I)


def _clean_title(text: str) -> str:
    return re.sub(r"</?em>", "", text or "").replace("red_beg", "").replace("red_end", "").strip()


def append_sogou_k_h(url: str) -> str:
    """WechatSogou #238：/link?url= 跳转需追加 k/h 随机参数。"""
    if not url or "&k=" in url:
        return url
    idx = url.find("url=")
    if idx == -1:
        return url
    b = math.floor(random.random() * 100) + 1
    pos = idx + 15 + b
    if pos >= len(url):
        return url
    h = url[pos]
    return f"{url}&k={b}&h={h}"


def _warmup_sogou_session(http: httpx.Client) -> None:
    """预取 SNUID/SUID 等 cookie（公开页面即可）。"""
    try:
        http.get("https://weixin.sogou.com/", headers={"User-Agent": UA})
        http.get(
            "https://www.sogou.com/sug/css/m3.min.v.7.css",
            headers={"User-Agent": UA, "Referer": SOGOU_WEIXIN},
        )
    except Exception:
        pass


def _parse_mp_url_from_js(text: str) -> str | None:
    """从跳转页 JS 拼接 mp.weixin 链接（支持 var url = '' 新格式）。"""
    base_parts = re.findall(r"var url = '([^']*)'", text)
    parts = re.findall(r"url \+= '([^']+)'", text)
    if parts:
        mp = (base_parts[0] if base_parts else "") + "".join(parts)
        mp = mp.replace("@", "").strip()
        if "mp.weixin.qq.com" in mp:
            return mp.split("#")[0]
    m = MP_WECHAT_RE.search(text)
    if m:
        return m.group(0).split("#")[0]
    return None


def parse_sogou_article_search_html(html: str) -> list[dict]:
    """解析搜狗微信文章搜索结果（type=2）。"""
    soup = BeautifulSoup(html or "", "lxml")
    out: list[dict] = []
    for li in soup.select("ul.news-list > li"):
        link = li.select_one("h3 a") or li.select_one("div h3 a") or li.select_one("a[href*='link?url=']")
        if not link:
            continue
        href = (link.get("href") or "").strip()
        title = _clean_title(link.get_text(" ", strip=True))
        abstract_el = li.select_one("p")
        abstract = _clean_title(abstract_el.get_text(" ", strip=True) if abstract_el else "")
        gzh_el = li.select_one("a[data-headimage]") or li.select_one("div a[data-isv]")
        account = (gzh_el.get_text(strip=True) if gzh_el else "").strip()
        if not href or not title:
            continue
        out.append(
            {
                "title": title[:200],
                "url": urljoin(SOGOU_WEIXIN, href) if href.startswith("/") else href,
                "abstract": abstract[:400],
                "account": account[:60],
                "from": "sogou",
            }
        )
    return out


def resolve_sogou_link(
    sogou_url: str,
    *,
    referer: str,
    http: httpx.Client | None = None,
    timeout: float = 20.0,
) -> str | None:
    """将搜狗跳转链解析为 mp.weixin.qq.com 文章 URL（同 session + k/h）。"""
    if MP_WECHAT_RE.search(sogou_url or ""):
        u = sogou_url.split("#")[0]
        if "/s/" in u:
            return u.split("?")[0]
        return u
    if not sogou_url or "link?url=" not in sogou_url:
        return None

    link = append_sogou_k_h(sogou_url)
    headers = {"User-Agent": UA, "Referer": referer}

    def _resolve(client: httpx.Client) -> str | None:
        resp = client.get(link, headers=headers)
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("location") or ""
            if MP_WECHAT_RE.search(loc):
                return loc.split("#")[0]
        text = resp.text or ""
        if "验证码" in text or "antispider" in str(resp.url):
            return None
        return _parse_mp_url_from_js(text)

    try:
        if http is not None:
            return _resolve(http)
        with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
            _warmup_sogou_session(client)
            return _resolve(client)
    except Exception as e:
        logger.warning("resolve_sogou_link failed %s: %s", sogou_url[:80], e)
    return None


def search_wechat_articles(
    query: str,
    *,
    page: int = 1,
    max_results: int = 10,
    timeout: float = 20.0,
) -> list[dict]:
    """搜狗搜微信文章，返回带 mp.weixin 链接的结果。"""
    q = (query or "").strip()
    if not q:
        return []
    referer = f"{SOGOU_WEIXIN}?type=2&query={quote(q)}"
    headers = {"User-Agent": UA, "Referer": "https://weixin.sogou.com/"}
    raw: list[dict] = []
    out: list[dict] = []

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as http:
            _warmup_sogou_session(http)
            resp = http.get(
                SOGOU_WEIXIN,
                params={"type": "2", "query": q, "page": str(page), "ie": "utf8"},
            )
            resp.raise_for_status()
            if "验证码" in resp.text or "antispider" in str(resp.url):
                logger.warning("sogou search captcha query=%s", q[:40])
                return []
            raw = parse_sogou_article_search_html(resp.text)
            for row in raw:
                if len(out) >= max_results:
                    break
                mp_url = resolve_sogou_link(row["url"], referer=referer, http=http, timeout=timeout)
                if not mp_url:
                    continue
                out.append({**row, "url": mp_url, "sogou_url": row["url"]})
                time.sleep(0.3)
    except Exception as e:
        logger.warning("sogou search failed query=%s: %s", q[:40], e)
        return []

    logger.info("sogou wechat search query=%s hits=%d resolved=%d", q[:40], len(raw), len(out))
    return out


def search_wechat_accounts(query: str, *, page: int = 1, timeout: float = 20.0) -> list[dict]:
    """搜狗搜公众号（type=1），返回 profile_url 等元信息。"""
    q = (query or "").strip()
    if not q:
        return []
    headers = {"User-Agent": UA, "Referer": "https://weixin.sogou.com/"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as http:
            _warmup_sogou_session(http)
            resp = http.get(
                SOGOU_WEIXIN,
                params={"type": "1", "query": q, "page": str(page), "ie": "utf8"},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            out: list[dict] = []
            for li in soup.select("ul.news-list2 > li"):
                a = li.select_one("div div a")
                name_el = li.select_one("p")
                if not a:
                    continue
                href = urljoin(SOGOU_WEIXIN, a.get("href", ""))
                name = _clean_title(name_el.get_text(" ", strip=True) if name_el else "")
                intro_el = li.select_one("dd")
                intro = (intro_el.get_text(strip=True) if intro_el else "")[:200]
                if name:
                    out.append({"wechat_name": name, "profile_url": href, "introduction": intro, "from": "sogou_account"})
            return out
    except Exception as e:
        logger.warning("sogou account search failed query=%s: %s", q[:40], e)
        return []
