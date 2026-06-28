"""统一页面抓取：httpx + Playwright（子进程，兼容 Windows uvicorn）。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.crawlers.base import JobPosting

logger = logging.getLogger(__name__)
T = TypeVar("T")
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class PageContent:
    url: str
    html: str
    text: str
    status_code: int = 200


def _run_playwright_subprocess(args: list[str], timeout: float) -> dict:
    cmd = [sys.executable, "-m", "app.crawlers.playwright_worker", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        timeout=timeout + 30,
    )
    stdout = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr or stdout or f"exit {proc.returncode}"
        raise RuntimeError(err[:500])
    return json.loads(stdout)


def _playwright_fetch_sync(
    url: str,
    user_agent: str,
    wait_ms: int,
    timeout: float,
    wait_until: str,
) -> PageContent:
    data = _run_playwright_subprocess(
        [url, user_agent, str(wait_ms), str(int(timeout * 1000)), wait_until, "fetch"],
        timeout,
    )
    return PageContent(url=data["url"], html=data["html"], text=data["text"])


def _playwright_parse_sync(
    url: str,
    user_agent: str,
    wait_ms: int,
    timeout: float,
    wait_until: str,
    mode: str,
    source: dict,
) -> list[JobPosting]:
    data = _run_playwright_subprocess(
        [
            url,
            user_agent,
            str(wait_ms),
            str(int(timeout * 1000)),
            wait_until,
            mode,
            json.dumps(source, ensure_ascii=False),
        ],
        timeout,
    )
    jobs: list[JobPosting] = []
    for raw in data.get("jobs") or []:
        jobs.append(JobPosting(**raw))
    return jobs


class CrawlFetcher:
    """单次 crawl 批次复用限速；Playwright 在子进程运行。"""

    def __init__(self, compliance: dict | None = None):
        c = compliance or {}
        self.rate_limit_rps = float(c.get("rate_limit_rps", 0.5))
        self.respect_robots = bool(c.get("respect_robots", True))
        self.user_agent = c.get("user_agent", "ResumeAI-Crawler/1.0")
        self.robots_bypass_domains = tuple(c.get("robots_bypass_domains") or [])
        self._min_interval = 1.0 / self.rate_limit_rps if self.rate_limit_rps > 0 else 0.0
        self._last_fetch = 0.0
        self._robots: dict[str, RobotFileParser] = {}

    def _bypass_robots(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(d in host for d in self.robots_bypass_domains)

    async def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        now = asyncio.get_event_loop().time()
        wait = self._min_interval - (now - self._last_fetch)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_fetch = asyncio.get_event_loop().time()

    async def _allowed(self, url: str) -> bool:
        if not self.respect_robots or self._bypass_robots(url):
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                await asyncio.to_thread(rp.read)
            except Exception:
                pass
            self._robots[base] = rp
        try:
            return self._robots[base].can_fetch(self.user_agent, url)
        except Exception:
            return True

    async def fetch_http(self, url: str, timeout: float = 20.0) -> PageContent:
        if not await self._allowed(url):
            raise PermissionError(f"robots.txt disallows: {url}")
        await self._throttle()
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            resp = await client.get(url)
            html = resp.text
            text = _html_to_text(html)
            return PageContent(url=str(resp.url), html=html, text=text, status_code=resp.status_code)

    async def fetch_playwright(
        self,
        url: str,
        wait_ms: int = 2500,
        timeout: float = 60.0,
        wait_until: str = "networkidle",
    ) -> PageContent:
        if not await self._allowed(url):
            raise PermissionError(f"robots.txt disallows: {url}")
        await self._throttle()
        return await asyncio.to_thread(
            _playwright_fetch_sync,
            url,
            self.user_agent,
            wait_ms,
            timeout,
            wait_until,
        )

    async def run_on_page(
        self,
        url: str,
        action: Callable[..., T],
        *args,
        wait_ms: int = 2500,
        timeout: float = 60.0,
        wait_until: str = "networkidle",
        ignore_robots: bool = False,
        parser_mode: str = "",
        **kwargs,
    ) -> T:
        old = self.respect_robots
        if ignore_robots:
            self.respect_robots = False
        try:
            if not parser_mode:
                raise ValueError("parser_mode required for subprocess playwright parse")
            if not await self._allowed(url):
                raise PermissionError(f"robots.txt disallows: {url}")
            await self._throttle()
            source = args[0] if args else {}
            return await asyncio.to_thread(
                _playwright_parse_sync,
                url,
                self.user_agent,
                wait_ms,
                timeout,
                wait_until,
                parser_mode,
                source,
            )
        finally:
            self.respect_robots = old

    async def fetch(
        self,
        url: str,
        *,
        use_playwright: bool = False,
        ignore_robots: bool = False,
        wait_until: str = "networkidle",
        **kwargs,
    ) -> PageContent:
        if ignore_robots:
            old = self.respect_robots
            self.respect_robots = False
            try:
                if use_playwright:
                    return await self.fetch_playwright(url, wait_until=wait_until, **kwargs)
                try:
                    return await self.fetch_http(url, **kwargs)
                except Exception as e:
                    logger.warning("HTTP fetch failed for %s: %s, retry with Playwright", url, e)
                    return await self.fetch_playwright(url, wait_until=wait_until, **kwargs)
            finally:
                self.respect_robots = old
        if use_playwright:
            return await self.fetch_playwright(url, wait_until=wait_until, **kwargs)
        try:
            return await self.fetch_http(url, **kwargs)
        except Exception as e:
            logger.warning("HTTP fetch failed for %s: %s, retry with Playwright", url, e)
            return await self.fetch_playwright(url, wait_until=wait_until, **kwargs)

    async def close(self) -> None:
        return


def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "lxml").get_text("\n", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", "\n", html)
