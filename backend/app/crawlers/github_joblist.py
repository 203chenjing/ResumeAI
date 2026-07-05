"""GitHub 每日校招仓库 Provider（S1）：零 token、零 Playwright、高时效。

解析社区维护的 markdown 表格 / JSON（SimplifyJobs、speedyapply、namewyf/Campus2026 等），
这些仓库公开、MIT、每日更新、自带投递链接与内推码，是合规高 ROI 数据源。
"""
from __future__ import annotations

import json
import logging
import re
import uuid

import asyncio
import httpx

from app.crawlers.base import CrawlerProvider, JobPosting
from app.crawlers.fetcher import CrawlFetcher
from app.services.job_validator import is_china_location

logger = logging.getLogger(__name__)

GH_MIRROR_PREFIXES = (
    "",
    "https://ghfast.top/",
)


async def _get_with_retry(http: httpx.AsyncClient, url: str, *, retries: int = 3) -> httpx.Response:
    last_err: Exception | None = None
    for attempt in range(retries):
        for prefix in GH_MIRROR_PREFIXES:
            target = url if not prefix else f"{prefix}{url}"
            try:
                resp = await http.get(target)
                resp.raise_for_status()
                if len(resp.text) > 50:
                    return resp
            except Exception as e:
                last_err = e
                logger.debug("github fetch failed %s attempt=%s: %s", target[:70], attempt + 1, e)
        if attempt < retries - 1:
            await asyncio.sleep(1.5 * (attempt + 1))
    raise last_err or RuntimeError(f"github fetch failed: {url[:80]}")

MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,4}\s+(.*\S)\s*$")
# 中文内推码常为纯字母（如 DBQMSUOJ / NTAciAS），故不强制要求数字；
# 仅在出现明确「内推码 / 内推 / 邀请码 / referral code」标记时抽取，避免误判。
REFERRAL_RE = re.compile(
    r"(?:内推码|内推|邀请码|referral code|invite code)[：:\s]*([A-Za-z][A-Za-z0-9]{3,11})"
)
CLOSED_MARKERS = ("🔒", "closed", "已结束", "已截止", "expired", "已停止", "已关闭")

# 仅作为分类锚点、不是公司名的标题（用于 heading-aware 解析时跳过）。
CATEGORY_HEADINGS = frozenset(
    {
        "目录导航", "26春招岗", "26秋招岗", "春招岗", "秋招岗", "大厂岗", "中厂", "大厂",
        "独角兽", "国企", "央企", "外企", "优质潜力企业", "潜力企业", "开发岗", "算法岗",
        "测试", "测试/运维/安全岗", "产品", "运营", "设计岗", "硬件岗", "金融岗",
        "实习篇", "校招篇", "目录", "简介", "前言", "说明", "贡献", "免责声明",
    }
)


def _strip_md(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"[*_`#]", "", text)
    text = re.sub(r"[🔥🎓💼🚀📈📂🎯🏢✅❌📚🤖📱📈🔽🔼]", "", text)
    return " ".join(text.split()).strip()


def _clean_heading(line: str) -> str:
    m = HEADING_RE.match(line)
    if not m:
        return ""
    title = _strip_md(m.group(1))
    title = re.sub(r"^\d+[\.、\s]*", "", title)  # 去掉前导编号
    return title.strip()


def _first_link(cell: str) -> tuple[str, str]:
    """返回 (显示文本, url)。"""
    m = MD_LINK_RE.search(cell or "")
    if m:
        return _strip_md(m.group(1)), m.group(2).strip()
    return _strip_md(cell), ""


REFERRAL_STOPWORDS = frozenset({"http", "https", "www", "com", "code", "link"})


def _extract_referral(row_text: str) -> str:
    m = REFERRAL_RE.search(row_text or "")
    if not m:
        return ""
    code = m.group(1)
    if code.lower() in REFERRAL_STOPWORDS:
        return ""
    return code


def _first_link_in_row(cells: list[str]) -> str:
    """整行扫描第一个 markdown 链接 URL（用于无明确链接列的表格）。"""
    for c in cells:
        m = MD_LINK_RE.search(c or "")
        if m:
            return m.group(2).strip()
    return ""


def _parse_markdown_table(md: str, source: dict, china_only: bool = False) -> list[JobPosting]:
    """解析 README 中的岗位表格。

    支持两种常见结构：
    1. 行内含公司列（namewyf/Campus2026）。
    2. 公司在「## 章节标题」、表格仅含岗位/链接（0voice 等）→ heading-aware。
    """
    jobs: list[JobPosting] = []
    channel = source.get("channel", "GitHub校招仓库")
    base_tags = [t for t in (source.get("tags") or ["校招", "GitHub"]) if t]
    max_items = int(source.get("max_items", 200))

    lines = md.splitlines()
    header: list[str] | None = None
    col_idx: dict[str, int] = {}
    current_company = ""

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            heading = _clean_heading(line)
            if heading and heading not in CATEGORY_HEADINGS and len(heading) <= 24:
                current_company = heading
            header = None
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = [_strip_md(c).lower() for c in cells]
            col_idx = {}
            for i, h in enumerate(header):
                if any(k in h for k in ("company", "公司", "企业", "name")) and "company" not in col_idx:
                    col_idx["company"] = i
                elif any(k in h for k in ("role", "position", "title", "岗位", "职位", "工作")):
                    col_idx["role"] = i
                elif any(k in h for k in ("location", "地点", "城市", "loc")):
                    col_idx["location"] = i
                elif any(k in h for k in ("link", "apply", "投递", "链接", "application", "内容", "详情", "查看", "状态", "备注")):
                    col_idx.setdefault("link", i)
                elif any(k in h for k in ("date", "更新", "age", "posted")):
                    col_idx["date"] = i
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue  # 分隔行
        if "company" not in col_idx and "role" not in col_idx:
            continue

        row_text = " ".join(cells)
        if any(m in row_text.lower() for m in CLOSED_MARKERS):
            continue

        def cell(key: str) -> str:
            i = col_idx.get(key, -1)
            return cells[i] if 0 <= i < len(cells) else ""

        company_disp, company_url = _first_link(cell("company"))
        role_disp, role_url = _first_link(cell("role"))
        loc = _strip_md(cell("location"))
        link_disp, link_url = _first_link(cell("link"))

        jd_url = link_url or role_url or company_url or _first_link_in_row(cells)
        company = company_disp or current_company or "未知企业"
        role = role_disp or link_disp or "校招岗位"
        if (not company or company == "未知企业") and len(role) < 3:
            continue

        referral = _extract_referral(row_text)
        locations = [p.strip() for p in re.split(r"[、,/，|]", loc) if p.strip()][:6]

        if china_only and not is_china_location(f"{loc} {company} {role}"):
            continue

        jobs.append(
            JobPosting(
                id=uuid.uuid4().hex[:12],
                company=company[:60],
                role=role[:120],
                source="github_joblist",
                jd_text=f"{company} {role} {loc}".strip(),
                jd_url=jd_url,
                location=locations[0] if locations else "",
                channel=channel,
                tags=list(base_tags),
                locations=locations,
                referral_code=referral,
                legitimacy="trusted",
                source_site=str(source.get("id") or ""),
            )
        )
        if len(jobs) >= max_items:
            break
    return jobs


def _parse_json_listings(payload: str, source: dict, china_only: bool = False) -> list[JobPosting]:
    """解析 .json 形式的岗位列表（speedyapply 等）。"""
    jobs: list[JobPosting] = []
    channel = source.get("channel", "GitHub校招仓库")
    base_tags = [t for t in (source.get("tags") or ["校招", "GitHub"]) if t]
    max_items = int(source.get("max_items", 200))
    try:
        data = json.loads(payload)
    except Exception:
        return []
    rows = data if isinstance(data, list) else data.get("jobs") or data.get("listings") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("active") is False or row.get("is_visible") is False:
            continue
        company = str(row.get("company_name") or row.get("company") or "").strip()
        role = str(row.get("title") or row.get("role") or row.get("position") or "").strip()
        url = str(row.get("url") or row.get("apply_link") or row.get("link") or "").strip()
        locs_raw = row.get("locations") or row.get("location") or []
        if isinstance(locs_raw, str):
            locs = [p.strip() for p in re.split(r"[、,/，|]", locs_raw) if p.strip()]
        else:
            locs = [str(x).strip() for x in locs_raw if str(x).strip()]
        if not company or not role:
            continue
        if china_only and not is_china_location(f"{' '.join(locs)} {company} {role}"):
            continue
        jobs.append(
            JobPosting(
                id=uuid.uuid4().hex[:12],
                company=company[:60],
                role=role[:120],
                source="github_joblist",
                jd_text=f"{company} {role} {' '.join(locs)}".strip(),
                jd_url=url,
                location=locs[0] if locs else "",
                channel=channel,
                tags=list(base_tags),
                locations=locs[:6],
                legitimacy="trusted",
                source_site=str(source.get("id") or ""),
            )
        )
        if len(jobs) >= max_items:
            break
    return jobs


class GithubJoblistProvider(CrawlerProvider):
    name = "github_joblist"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: CrawlFetcher | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        if not config.get("enabled", True):
            return []

        china_only = bool(config.get("china_only", False))
        ua = "ResumeAI-Crawler/1.0 (+github joblist consumer)"
        jobs: list[JobPosting] = []
        async with httpx.AsyncClient(
            timeout=45.0, follow_redirects=True, headers={"User-Agent": ua}
        ) as http:
            for source in config.get("sources") or []:
                if source.get("enabled") is False:
                    continue
                url = source.get("raw_url") or source.get("url", "")
                if not url:
                    continue
                sid = source.get("id", url)
                source_china = bool(source.get("china_only", china_only))
                try:
                    resp = await _get_with_retry(http, url)
                    body = resp.text
                    if url.endswith(".json") or source.get("format") == "json":
                        items = _parse_json_listings(body, source, china_only=source_china)
                    else:
                        items = _parse_markdown_table(body, source, china_only=source_china)
                    logger.info("github_joblist %s: %d jobs", sid, len(items))
                    jobs.extend(items)
                except Exception as e:
                    logger.warning("github_joblist %s failed: %s", sid, e)
        return jobs
