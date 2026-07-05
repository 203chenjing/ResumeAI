"""公开网页搜索：国内优先 Bing，DuckDuckGo / Playwright 兜底。"""
from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.crawlers.fetcher import _run_playwright_subprocess

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BING_SEARCH = "https://cn.bing.com/search"
DDG_SEARCH = "https://html.duckduckgo.com/html/"


def _clean_results(rows: list[dict], *, max_results: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        if not url.startswith("http") or not title:
            continue
        key = url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title[:200], "url": url, "snippet": (row.get("snippet") or "")[:400]})
        if len(out) >= max_results:
            break
    return out


def _parse_bing_html(html: str, *, max_results: int) -> list[dict]:
    soup = BeautifulSoup(html or "", "lxml")
    rows: list[dict] = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a:
            continue
        href = (a.get("href") or "").strip()
        title = " ".join(a.get_text(" ", strip=True).split())
        snippet_el = li.select_one(".b_caption p") or li.select_one("p")
        snippet = " ".join((snippet_el.get_text(" ", strip=True) if snippet_el else "").split())
        if href and title:
            rows.append({"title": title, "url": href, "snippet": snippet})
    return _clean_results(rows, max_results=max_results)


def _parse_ddg_html(html: str, *, max_results: int) -> list[dict]:
    soup = BeautifulSoup(html or "", "lxml")
    rows: list[dict] = []
    for result in soup.select(".result"):
        a = result.select_one("a.result__a")
        if not a:
            continue
        href = _normalize_ddg_href(a.get("href") or "")
        title = " ".join(a.get_text(" ", strip=True).split())
        snippet_el = result.select_one(".result__snippet")
        snippet = " ".join((snippet_el.get_text(" ", strip=True) if snippet_el else "").split())
        if href and title:
            rows.append({"title": title, "url": href, "snippet": snippet})
    return _clean_results(rows, max_results=max_results)


def _normalize_ddg_href(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com/l/" in href and parsed.query:
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    return href


def _bing_search_httpx(query: str, *, max_results: int, timeout: float) -> list[dict]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": UA}) as http:
            resp = http.get(BING_SEARCH, params={"q": query, "setlang": "zh-Hans"})
            resp.raise_for_status()
            hits = _parse_bing_html(resp.text, max_results=max_results)
            if hits:
                logger.info("bing httpx search ok query=%s hits=%d", query[:40], len(hits))
            return hits
    except Exception as e:
        logger.warning("bing httpx search failed query=%s: %s", query[:40], e)
        return []


def _ddg_search_httpx(query: str, *, max_results: int, timeout: float) -> list[dict]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": UA}) as http:
            resp = http.post(DDG_SEARCH, data={"q": query, "b": "", "kl": "cn-zh"})
            resp.raise_for_status()
            return _parse_ddg_html(resp.text, max_results=max_results)
    except Exception as e:
        logger.warning("ddg httpx search failed query=%s: %s", query[:40], e)
        return []


async def web_search(query: str, *, max_results: int = 8) -> list[dict]:
    """异步搜索（供 search_discovery）。"""
    q = (query or "").strip()
    if not q:
        return []
    timeout = 20.0
    hits = _bing_search_httpx(q, max_results=max_results, timeout=timeout)
    if hits:
        return hits
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": UA}) as http:
            resp = await http.post(DDG_SEARCH, data={"q": q, "b": "", "kl": "cn-zh"})
            resp.raise_for_status()
            return _parse_ddg_html(resp.text, max_results=max_results)
    except Exception:
        logger.exception("web_search all engines failed query=%s", q[:80])
        return []


def browser_search_sync(
    query: str,
    user_agent: str,
    max_results: int,
    timeout: float,
) -> list[dict]:
    """同步搜索（供 Playwright 流水线）：Bing httpx → Playwright Bing → Playwright DDG。"""
    q = (query or "").strip()
    if not q:
        return []

    hits = _bing_search_httpx(q, max_results=max_results, timeout=min(timeout, 25.0))
    if hits:
        return hits

    hits = _ddg_search_httpx(q, max_results=max_results, timeout=min(timeout, 20.0))
    if hits:
        return hits

    bing_url = f"{BING_SEARCH}?q={quote(q)}&setlang=zh-Hans"
    for mode, url in (
        ("search_bing", bing_url),
        ("search_ddg", f"{DDG_SEARCH}?q={quote(q)}"),
    ):
        try:
            data = _run_playwright_subprocess(
                [
                    url,
                    user_agent or UA,
                    "2000",
                    str(int(timeout * 1000)),
                    "domcontentloaded",
                    mode,
                    str(max_results),
                ],
                timeout,
            )
            results = list(data.get("results") or [])
            if results:
                logger.info("browser search %s ok query=%s hits=%d", mode, q[:40], len(results))
                return results
        except Exception as e:
            logger.warning("browser search %s failed query=%s: %s", mode, q[:40], e)
    return []
