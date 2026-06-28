"""岗位列表解析器。"""
from __future__ import annotations

import hashlib
import re
import uuid
from urllib.parse import urljoin

from dataclasses import replace

from app.crawlers.base import JobPosting

JOB_KEYWORDS = ("招聘", "宣讲", "校招", "实习", "双选", "招聘会", "岗位", "人才")
COMPANY_SUFFIXES = (
    "有限公司",
    "股份有限公司",
    "研究院",
    "研究所",
    "大学",
    "学院",
    "银行",
    "集团",
    "科技",
    "证券",
    "基金",
    "医院",
    "学校",
)

TITLE_NOISE = re.compile(r"^(首页|更多|下一页|上一页|招聘信息|宣讲会|实习信息|职位|筛选|搜索).*$")

CAREER_ARTICLE_KEYWORDS = (
    "汇总",
    "指导中心",
    "职业发展",
    "选调生信息",
    "双选会",
    "宣讲会安排",
    "专场安排",
    "活动安排",
    "通知公告",
    "信息发布",
    "行程发布",
    "地域行",
    "实践活动",
    "实践招募",
    "版权所有",
    "地址：",
    "联系我们",
)

UNIVERSITY_MARKERS = ("大学", "学院", "学校", "职介中心", "就业指导")

NOWCODER_CARD_RE = re.compile(
    r"^(?P<company>.+?)\s+(?P<role>\d+(?:届)?(?:实习|校招|提前批|补录|秋招|春招))"
    r"\s*[丨|]\s*"
    r"(?:(?P<published>\d+\.\d+)收录\s*)?"
    r"(?:地点[：:]\s*(?P<location>.+?))?"
    r"(?:\s*立即投递)?\s*$"
)

NOWCODER_FIELD_RE = {
    "batch": re.compile(r"招聘批次[：:]\s*([^\n]+)"),
    "deadline": re.compile(r"网申时间[：:]\s*([^\n]+)"),
    "city": re.compile(r"招聘城市[：:]\s*([^\n]+)"),
    "positions": re.compile(r"招聘岗位[：:]\s*([^\n]+)"),
}


def _normalize_company_name(name: str) -> str:
    cleaned = " ".join(name.split()).strip()
    if re.search(r"[\u4e00-\u9fff]", cleaned) and " " in cleaned:
        return re.sub(r"\s+", "", cleaned)
    return cleaned


def parse_nowcoder_card_text(text: str) -> dict[str, str]:
    """解析牛客校招日程卡片文案。"""
    line = re.sub(r"\s*立即投递\s*$", "", " ".join(text.split()).strip())
    m = NOWCODER_CARD_RE.match(line)
    if not m:
        return {}
    location = (m.group("location") or "").strip(" ：:")
    return {
        "company": _normalize_company_name(m.group("company")),
        "role": m.group("role").strip(),
        "published": (m.group("published") or "").strip(),
        "location": location,
    }


def parse_nowcoder_enterprise_text(text: str) -> dict[str, str]:
    """解析牛客企业校招详情页结构化字段。"""
    out: dict[str, str] = {}
    for key, pattern in NOWCODER_FIELD_RE.items():
        m = pattern.search(text)
        if m:
            out[key] = m.group(1).strip()
    return out


def split_position_titles(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[、,/，|]", raw)
    titles = [p.strip() for p in parts if len(p.strip()) >= 2]
    return titles[:20]


def _job_id(source_id: str, key: str) -> str:
    return hashlib.sha256(f"{source_id}:{key}".encode()).hexdigest()[:12]


def attach_source_meta(jobs: list[JobPosting], source: dict) -> list[JobPosting]:
    """把 YAML 来源地、站点 id 写入岗位。"""
    city = (source.get("city") or "").strip()
    site = (source.get("id") or "").strip()
    out: list[JobPosting] = []
    for job in jobs:
        loc = job.location.strip() if job.location else ""
        locs = list(job.locations)
        if loc and loc not in locs:
            locs.insert(0, loc)
        out.append(
            replace(
                job,
                city=city or job.city,
                source_site=site or job.source_site,
                locations=locs,
            )
        )
    return out


def _is_likely_university(name: str) -> bool:
    n = (name or "").strip()
    if not n or len(n) > 24:
        return False
    return any(m in n for m in UNIVERSITY_MARKERS)


def _is_career_article_title(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 10:
        return True
    if any(k in t for k in CAREER_ARTICLE_KEYWORDS):
        return True
    if t.startswith("地址") or "版权所有" in t:
        return True
    return False


def _extract_employer_from_title(text: str) -> str:
    m = re.search(r"【([^】]{2,40})】", text)
    if m and not _is_likely_university(m.group(1)):
        return _normalize_company_name(m.group(1))
    for suf in COMPANY_SUFFIXES:
        if suf in ("大学", "学院", "学校"):
            continue
        m = re.search(rf"([\u4e00-\u9fffA-Za-z0-9（）()·]{{2,30}}{re.escape(suf)})", text)
        if m and not _is_likely_university(m.group(1)):
            return _normalize_company_name(m.group(1))
    return ""


def _guess_company(text: str, *, allow_university: bool = True) -> str:
    for suf in COMPANY_SUFFIXES:
        if not allow_university and suf in ("大学", "学院", "学校"):
            continue
        m = re.search(rf"([\u4e00-\u9fffA-Za-z0-9（）()·]+{re.escape(suf)})", text)
        if m:
            name = _normalize_company_name(m.group(1))
            if not allow_university and _is_likely_university(name):
                continue
            return name[:60]
    m = re.search(r"【([^】]{4,40})】", text)
    if m:
        name = m.group(1)
        if allow_university or not _is_likely_university(name):
            return name
    return ""


def _build_university_job_tags(tags: list[str] | None, publisher: str) -> list[str]:
    out = [t for t in (tags or []) if t]
    if publisher:
        pub_tag = f"发布方:{publisher}"
        if pub_tag not in out:
            out.insert(0, pub_tag)
    return out


def _guess_role(text: str, company: str) -> str:
    cleaned = text
    if company:
        cleaned = cleaned.replace(company, "")
    cleaned = re.sub(r"【[^】]*】", "", cleaned).strip()
    if len(cleaned) > 8:
        return cleaned[:80]
    return text[:80]


def parse_text_lines(
    text: str,
    *,
    source_id: str,
    source_name: str,
    channel: str,
    base_url: str,
    source_type: str = "university_html",
    tags: list[str] | None = None,
    max_items: int = 40,
) -> list[JobPosting]:
    """从渲染后的纯文本提取岗位行（高校就业网通用）。"""
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    is_university = source_type == "university_html"

    for raw_line in text.split("\n"):
        line = " ".join(raw_line.split()).strip()
        if len(line) < 12 or len(line) > 300:
            continue
        if TITLE_NOISE.match(line):
            continue
        if is_university and _is_career_article_title(line):
            continue
        if not any(k in line for k in JOB_KEYWORDS) and not _guess_company(line, allow_university=not is_university):
            continue

        if is_university:
            employer = _extract_employer_from_title(line) or _guess_company(line, allow_university=False)
            company = employer or "招聘单位待确认"
            role = line
            if employer:
                role = _guess_role(line, employer)
            row_tags = _build_university_job_tags(tags, source_name)
        else:
            company = _guess_company(line) or source_name
            role = _guess_role(line, company)
            row_tags = list(tags or ["校招", source_name])

        key = line[:120]
        if key in seen:
            continue
        seen.add(key)

        jobs.append(
            JobPosting(
                id=_job_id(source_id, key),
                company=company,
                role=role,
                source=source_type,
                jd_text=line,
                jd_url=base_url,
                channel=channel,
                tags=row_tags,
            )
        )
        if len(jobs) >= max_items:
            break
    return jobs


def parse_html_links(
    html: str,
    *,
    source_id: str,
    source_name: str,
    channel: str,
    base_url: str,
    source_type: str = "university_html",
    link_pattern: str = "",
    tags: list[str] | None = None,
    max_items: int = 40,
) -> list[JobPosting]:
    """从 HTML 链接提取岗位（静态页 fallback）。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    jobs: list[JobPosting] = []
    seen: set[str] = set()

    is_university = source_type == "university_html"

    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text().split()).strip()
        href = a["href"]
        if len(text) < 8:
            continue
        if link_pattern and link_pattern not in href:
            continue
        if is_university and _is_career_article_title(text):
            continue
        if not any(k in text for k in JOB_KEYWORDS + COMPANY_SUFFIXES):
            continue
        key = text[:100]
        if key in seen:
            continue
        seen.add(key)

        if is_university:
            employer = _extract_employer_from_title(text) or _guess_company(text, allow_university=False)
            company = employer or "招聘单位待确认"
            role = text if not employer else _guess_role(text, employer)
            row_tags = _build_university_job_tags(tags, source_name)
        else:
            company = _guess_company(text) or source_name
            role = _guess_role(text, company)
            row_tags = list(tags or ["校招", source_name])

        jobs.append(
            JobPosting(
                id=_job_id(source_id, key),
                company=company,
                role=role,
                source=source_type,
                jd_text=text,
                jd_url=urljoin(base_url, href),
                channel=channel,
                tags=row_tags,
            )
        )
        if len(jobs) >= max_items:
            break
    return jobs


def parse_nowcoder_schedule(page, source: dict) -> list[JobPosting]:
    """牛客网校招日程：解析企业卡片并尽量拉取详情页招聘岗位。"""
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    source_id = source.get("id", "nowcoder")
    tags = [t for t in (source.get("tags") or ["校招", "牛客"]) if t not in ("聚合", "job_aggregator")]
    enrich_detail = bool(source.get("enrich_detail", True))
    max_items = int(source.get("max_items", 60))
    schedule_url = page.url

    entries: list[tuple[str, str]] = []
    for sel in ("a[href*='enterprise']", "a[href*='jump?type=ad']"):
        for a in page.query_selector_all(sel):
            href = a.get_attribute("href") or ""
            text = " ".join(a.inner_text().split())
            if len(text) < 8 or href in seen:
                continue
            if not any(k in text for k in ("校招", "实习", "提前批", "补录", "届")):
                continue
            seen.add(href)
            entries.append((href, text))
            if len(entries) >= max_items:
                break
        if len(entries) >= max_items:
            break

    for href, text in entries:
        card = parse_nowcoder_card_text(text)
        company = card.get("company") or _guess_company(text) or "未知企业"
        batch = card.get("role") or ""
        location = card.get("location") or ""
        published = card.get("published") or ""
        detail: dict[str, str] = {}

        full_url = urljoin("https://www.nowcoder.com", href)
        if enrich_detail and "/enterprise/" in href:
            try:
                page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(int(source.get("detail_wait_ms", 1500)))
                detail = parse_nowcoder_enterprise_text(page.inner_text("body"))
            except Exception:
                detail = {}

        deadline = detail.get("deadline", "")
        city = detail.get("city") or location
        batch = detail.get("batch") or batch
        positions = split_position_titles(detail.get("positions", ""))

        summary_bits = [f"{company} {batch}".strip()]
        if city:
            summary_bits.append(f"工作地：{city}")
        if deadline:
            summary_bits.append(f"网申：{deadline}")
        if published:
            summary_bits.append(f"收录：{published}")
        summary = "；".join(summary_bits)

        if positions:
            for pos in positions:
                role = pos if pos != batch else f"{pos}（{batch}）" if batch else pos
                jd_text = f"{summary}\n招聘岗位：{pos}"
                jobs.append(
                    JobPosting(
                        id=_job_id(source_id, f"{href}:{pos}"),
                        company=company,
                        role=role[:100],
                        source="job_aggregator",
                        jd_text=jd_text[:500],
                        jd_url=full_url,
                        location=city,
                        deadline=deadline,
                        channel="牛客校招日程",
                        tags=tags,
                    )
                )
        else:
            role = batch or _guess_role(text, company)
            jobs.append(
                JobPosting(
                    id=_job_id(source_id, href),
                    company=company,
                    role=role[:100],
                    source="job_aggregator",
                    jd_text=summary[:500] if summary else text[:500],
                    jd_url=full_url,
                    location=city,
                    deadline=deadline,
                    channel="牛客校招日程",
                    tags=tags,
                )
            )

    if schedule_url and schedule_url != page.url:
        try:
            page.goto(schedule_url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

    return jobs[:max_items * 3]


def parse_yingjiesheng_list(page, source: dict) -> list[JobPosting]:
    """应届生求职网：解析职位链接（公开列表页）。"""
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    source_id = source.get("id", "yjs")
    tags = source.get("tags") or ["校招", "应届生求职网", "聚合"]

    anchors = page.query_selector_all(
        "a[href*='yingjiesheng.com/job'], a[href*='my.yingjiesheng.com/job']"
    )
    for a in anchors:
        href = a.get_attribute("href") or ""
        text = " ".join(a.inner_text().split())
        if len(text) < 10 or href in seen:
            continue
        seen.add(href)
        company = _guess_company(text) or text.split()[0][:30]
        role = _guess_role(text, company)
        loc_m = re.search(r"\[([^\]]+)\]", text)
        location = loc_m.group(1) if loc_m else ""
        jobs.append(
            JobPosting(
                id=_job_id(source_id, href),
                company=company,
                role=role,
                source="job_aggregator",
                jd_text=text,
                jd_url=href,
                location=location,
                channel="应届生求职网",
                tags=tags,
            )
        )
    return jobs[: int(source.get("max_items", 50))]


def parse_bytedance_campus(page, source: dict) -> list[JobPosting]:
    """字节跳动校招页：解析职位卡片链接。"""
    jobs: list[JobPosting] = []
    anchors = page.query_selector_all("a[href*='/campus/position/'][href*='detail']")
    seen: set[str] = set()
    base = "https://jobs.bytedance.com"

    for a in anchors:
        href = a.get_attribute("href") or ""
        text = " ".join(a.inner_text().split())
        if len(text) < 10 or href in seen:
            continue
        seen.add(href)
        full_url = urljoin(base, href)
        company = source.get("name", "字节跳动")
        jobs.append(
            JobPosting(
                id=_job_id(source.get("id", "bytedance"), href),
                company=company,
                role=text[:100],
                source="company_campus",
                jd_text=text,
                jd_url=full_url,
                channel="企业校招",
                tags=source.get("tags") or ["大厂", "校招"],
            )
        )
    return jobs[:50]


async def parse_source_page(
    fetcher,
    source: dict,
    provider_name: str,
) -> list[JobPosting]:
    """按 source.parser 调度解析。"""
    url = source.get("list_url") or source.get("url", "")
    if not url:
        return []

    parser = source.get("parser", "generic_list")
    use_pw = source.get("use_playwright", True)
    ignore_robots = (
        bool(source["ignore_robots"])
        if "ignore_robots" in source
        else provider_name == "university_html"
    )
    source_id = source.get("id", uuid.uuid4().hex[:8])
    name = source.get("name", source_id)
    channel = source.get("channel", "高校就业网" if provider_name == "university_html" else "企业校招")
    tags = source.get("tags") or []
    max_items = int(source.get("max_items", 40))
    wait_until = source.get("wait_until", "networkidle")
    pw_timeout = float(source.get("timeout", 60))
    pw_wait_ms = int(source.get("wait_ms", 3000))

    if parser == "bytedance_campus":
        if not ignore_robots and not fetcher._allowed(url):
            raise PermissionError(f"robots.txt disallows: {url}")
        jobs = await fetcher.run_on_page(
            url,
            parse_bytedance_campus,
            source,
            wait_ms=pw_wait_ms,
            timeout=pw_timeout,
            wait_until=wait_until,
            ignore_robots=ignore_robots,
            parser_mode="bytedance",
        )
        return attach_source_meta(jobs, source)

    if parser in ("nowcoder_schedule", "yingjiesheng_list"):
        if not ignore_robots and not fetcher._allowed(url):
            raise PermissionError(f"robots.txt disallows: {url}")
        fn = parse_nowcoder_schedule if parser == "nowcoder_schedule" else parse_yingjiesheng_list
        mode = "nowcoder" if parser == "nowcoder_schedule" else "yingjiesheng"
        jobs = await fetcher.run_on_page(
            url,
            fn,
            source,
            wait_ms=pw_wait_ms,
            timeout=pw_timeout,
            wait_until=wait_until,
            ignore_robots=ignore_robots,
            parser_mode=mode,
        )
        return attach_source_meta(jobs, source)

    page = await fetcher.fetch(
        url,
        use_playwright=use_pw,
        ignore_robots=ignore_robots,
        wait_ms=int(source.get("wait_ms", 2500)),
        wait_until=wait_until,
        timeout=pw_timeout,
    )

    if parser == "html_links":
        return attach_source_meta(
            parse_html_links(
                page.html,
                source_id=source_id,
                source_name=name,
                channel=channel,
                base_url=page.url,
                source_type=provider_name,
                link_pattern=source.get("link_pattern", ""),
                tags=tags,
                max_items=max_items,
            ),
            source,
        )

    jobs = parse_text_lines(
        page.text,
        source_id=source_id,
        source_name=name,
        channel=channel,
        base_url=page.url,
        source_type=provider_name,
        tags=tags,
        max_items=max_items,
    )
    if not jobs and page.html:
        jobs = parse_html_links(
            page.html,
            source_id=source_id,
            source_name=name,
            channel=channel,
            base_url=page.url,
            source_type=provider_name,
            tags=tags,
            max_items=max_items,
        )
    return attach_source_meta(jobs, source)
