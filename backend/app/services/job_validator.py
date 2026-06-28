"""岗位信息校验 + 来源地/标签 enrichment。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# 常见工作城市（用于从 JD 文本提取）
CITIES = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "苏州",
    "成都",
    "武汉",
    "西安",
    "合肥",
    "东莞",
    "厦门",
    "福州",
    "天津",
    "重庆",
    "长沙",
    "郑州",
    "青岛",
    "大连",
    "宁波",
    "无锡",
    "珠海",
    "佛山",
    "惠州",
    "雄安",
)

# 中国大陆地点判定（含在华外企常见城市的英文写法）。
CHINA_LOCATION_HINTS = (
    "中国", "大陆", "全国", "china", "mainland", "prc",
    "beijing", "shanghai", "shenzhen", "guangzhou", "hangzhou",
    "chengdu", "nanjing", "suzhou", "wuhan", "xi'an", "xian",
    "tianjin", "chongqing", "dalian", "ningbo", "xiamen", "hefei",
    "dongguan", "changsha", "qingdao", "zhuhai", "foshan", "wuxi",
)


def is_china_location(text: str) -> bool:
    """判断地点/文本是否指向中国大陆（含在华外企）。"""
    if not text:
        return False
    low = text.lower()
    if any(c in text for c in CITIES):
        return True
    return any(h in low for h in CHINA_LOCATION_HINTS)


NOISE_EXACT = frozenset(
    {
        "首页",
        "更多",
        "下一页",
        "上一页",
        "招聘信息",
        "宣讲会",
        "实习信息",
        "登录",
        "注册",
        "搜索",
        "筛选",
        "投递",
        "立即投递",
        "官网投递",
        "未知企业",
        "待确认公司",
    }
)

NOISE_SUBSTR = ("点击", "javascript:", "暂无数据", "404", "error page")

INTERNAL_TAGS = frozenset(
    {
        "job_aggregator",
        "company_campus",
        "university_html",
        "wechat_article",
        "聚合",
    }
)

SOURCE_LABELS = {
    "job_aggregator": "求职平台",
    "company_campus": "企业官网",
    "university_html": "高校就业网",
    "wechat_article": "公众号",
    "github_joblist": "GitHub校招库",
    "ats_board": "企业ATS",
}

# 这些来源为结构化官方/社区数据，字段干净但 JD 正文短，跳过严格正文校验。
TRUSTED_SOURCES = frozenset({"github_joblist", "ats_board"})

ARTICLE_TITLE_KEYWORDS = (
    "汇总",
    "指导中心",
    "职业发展",
    "选调生信息",
    "就业信息网",
    "招聘会",
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
    "京彩大创",
    "创新创业大赛",
    "洽谈会",
    "宣介",
    "人才宣介",
    "博士后",
    "开幕",
    "部署会",
    "公示",
    "关于公布",
    "关于举办",
    "关于召开",
    "报名通知",
    "赛事",
    "获奖名单",
)

NEWS_TITLE_PATTERNS = (
    re.compile(r"关于(公布|举办|召开|开展)"),
    re.compile(r"(大赛|洽谈会|宣介|开幕式|部署会|通知)(来[了啦]|顺|暨)"),
    re.compile(r"第五届|第四届|第三届"),
    re.compile(r"岗位合集"),
)

LIST_PAGE_PATH_MARKERS = (
    "/anony/xxfb",
    "/recruitmentinfoList",
    "/recruitmentFairList",
    "/recruitmentinfoList.html",
)

JOB_SIGNAL_RE = re.compile(
    r"(工程师|开发|算法|产品|运营|设计|管培|分析师|研究员|实习|校招|秋招|春招|提前批|补录|招聘)"
)

JOB_TYPE_RULES = (
    ("实习", "实习"),
    ("提前批", "提前批"),
    ("补录", "补录"),
    ("秋招", "秋招"),
    ("春招", "春招"),
    ("校招", "校招"),
    ("应届", "校招"),
    ("社招", "社招"),
)


def _clean(s: str) -> str:
    return " ".join((s or "").split()).strip()


def extract_locations(text: str) -> list[str]:
    """从 JD 文本提取工作城市。"""
    found: list[str] = []
    for city in CITIES:
        if city in text and city not in found:
            found.append(city)
    # 地点：北京/上海 格式
    for m in re.finditer(r"地点[：:\s]*([^\n]{2,40})", text):
        chunk = m.group(1)
        for city in CITIES:
            if city in chunk and city not in found:
                found.append(city)
    return found[:8]


def build_tags(job: dict) -> list[str]:
    """合并来源地、渠道、配置标签，去重保序（过滤内部实现标签）。"""
    tags: list[str] = []
    city = _clean(job.get("city", ""))
    if city:
        tags.append(f"来源:{city}")

    for loc in job.get("locations") or extract_locations(job.get("jd_text", "")):
        t = f"工作地:{loc}"
        if t not in tags:
            tags.append(t)

    channel = _clean(job.get("channel", ""))
    if channel:
        tags.append(channel)

    for t in job.get("tags") or []:
        t = str(t).strip()
        if not t or t in INTERNAL_TAGS:
            continue
        if t in tags or t.startswith("来源:") or t.startswith("工作地:"):
            continue
        tags.append(t)

    return tags[:12]


def infer_job_type(text: str) -> str:
    t = text or ""
    for kw, label in JOB_TYPE_RULES:
        if kw in t:
            return label
    return "校招"


def extract_published_at(text: str) -> str:
    """牛客等来源的「06.15收录」→ ISO 日期（当年）。"""
    m = re.search(r"(\d{2})\.(\d{2})收录", text or "")
    if not m:
        return ""
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return ""
    from datetime import datetime

    year = datetime.now().year
    return f"{year}-{month:02d}-{day:02d}"


def _is_list_page_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(m.lower() in path for m in LIST_PAGE_PATH_MARKERS)


def _looks_like_news_title(text: str) -> bool:
    t = text or ""
    if any(k in t for k in ARTICLE_TITLE_KEYWORDS):
        return True
    return any(p.search(t) for p in NEWS_TITLE_PATTERNS)


def _is_university_as_employer(company: str, publisher: str) -> bool:
    if not company:
        return False
    if publisher and company == publisher:
        return True
    if company.startswith("地址"):
        return True
    if any(m in company for m in ("大学", "学院", "学校", "职介", "就业指导")) and len(company) <= 24:
        return True
    return False


def _is_university_publisher_noise(company: str, role: str, jd_text: str, publisher: str) -> bool:
    blob = f"{role} {jd_text}"
    if publisher and company == publisher and _looks_like_news_title(blob):
        return True
    if _is_university_as_employer(company, publisher) and _looks_like_news_title(blob):
        return True
    if re.search(r"(大学|学院|学校|就业信息网)$", company) and _looks_like_news_title(blob):
        return True
    return False


def normalize_university_job(job: dict) -> dict:
    """高校就业网：学校是发布方，不是用人单位。"""
    out = dict(job)
    if out.get("source") != "university_html":
        return out

    tags = list(out.get("tags") or [])
    publisher = ""
    for t in tags:
        if str(t).startswith("发布方:"):
            publisher = str(t).replace("发布方:", "", 1).strip()
            break

    company = _clean(out.get("company", ""))
    blob = f"{out.get('role', '')} {out.get('jd_text', '')}"

    if _is_university_as_employer(company, publisher):
        from app.crawlers.parsers import _extract_employer_from_title

        employer = _extract_employer_from_title(blob)
        out["company"] = employer or "招聘单位待确认"
        if publisher and f"发布方:{publisher}" not in tags:
            tags.insert(0, f"发布方:{publisher}")
            out["tags"] = tags
    return out


def normalize_nowcoder_job(job: dict) -> dict:
    """修正牛客日程类岗位的历史脏数据（公司名/职位未拆分）。"""
    from app.crawlers.parsers import parse_nowcoder_card_text

    text = _clean(job.get("jd_text", "")) or _clean(job.get("role", ""))
    if "收录" not in text or "地点" not in text:
        return job

    parsed = parse_nowcoder_card_text(text)
    if not parsed:
        return job

    out = dict(job)
    if parsed.get("company"):
        out["company"] = parsed["company"]
    current_role = _clean(out.get("role", ""))
    if parsed.get("role") and (current_role == text or len(current_role) > 40):
        out["role"] = parsed["role"]
    if parsed.get("location") and not out.get("location"):
        out["location"] = parsed["location"]
    if parsed.get("published"):
        out["published_at"] = extract_published_at(f"{parsed['published']}收录")
    return out


def _validate_trusted(normalized: dict) -> dict:
    """结构化官方/社区来源：字段干净，仅做轻量校验与 enrichment。"""
    issues: list[str] = []
    company = _clean(normalized.get("company", ""))
    role = _clean(normalized.get("role", ""))
    jd_text = _clean(normalized.get("jd_text", ""))
    jd_url = _clean(normalized.get("jd_url", ""))

    if len(company) < 2:
        issues.append("公司名过短")
    if len(role) < 3:
        issues.append("岗位标题无效")

    status = "invalid" if issues else "ok"
    if status == "ok" and not jd_url:
        status = "weak"
        issues.append("无官方链接")

    locations = extract_locations(jd_text or normalized.get("location", ""))
    out = normalized
    out["company"] = company
    out["role"] = role[:200]
    out["jd_text"] = (jd_text or f"{company} {role}").strip()[:2000]
    out["locations"] = locations or normalized.get("locations") or []
    out["job_type"] = infer_job_type(f"{role} {jd_text}")
    if not out.get("legitimacy"):
        out["legitimacy"] = "trusted"
    out["validation_status"] = status
    out["validation_issues"] = issues
    out["tags"] = build_tags(out)
    return out


def validate_job(job: dict) -> dict:
    """
    校验岗位信息，返回 enrichment 后的 dict：
    - validation_status: ok | weak | invalid
    - validation_issues: list[str]
    - tags: 含来源地
    """
    normalized = normalize_university_job(normalize_nowcoder_job(dict(job)))

    if normalized.get("source") in TRUSTED_SOURCES:
        return _validate_trusted(normalized)

    issues: list[str] = []
    company = _clean(normalized.get("company", ""))
    role = _clean(normalized.get("role", ""))
    jd_text = _clean(normalized.get("jd_text", ""))
    jd_url = _clean(normalized.get("jd_url", ""))

    if len(company) < 2:
        issues.append("公司名过短")
    if company in NOISE_EXACT:
        issues.append("公司名为导航噪声")
    if any(n in company for n in NOISE_SUBSTR):
        issues.append("公司名含无效内容")

    if len(role) < 4 and len(jd_text) < 15:
        issues.append("岗位描述不足")

    if role in NOISE_EXACT or (len(role) < 6 and not jd_text):
        issues.append("岗位标题无效")

    if jd_url:
        try:
            p = urlparse(jd_url)
            if p.scheme not in ("http", "https"):
                issues.append("链接协议无效")
        except Exception:
            issues.append("链接格式无效")
    else:
        issues.append("无官方链接")

    # 聚合站重复标题：公司名≈整段 role
    if company and role == company:
        issues.append("标题过长疑似未解析")
    elif company and role.startswith(company) and len(role) > len(company) + 80:
        issues.append("标题过长疑似未解析")

    tags_list = normalized.get("tags") or []
    publisher = ""
    for t in tags_list:
        if str(t).startswith("发布方:"):
            publisher = str(t).replace("发布方:", "", 1).strip()
            break

    if _looks_like_news_title(role) or _looks_like_news_title(jd_text):
        issues.append("疑似资讯标题非具体岗位")

    if _is_university_publisher_noise(company, role, jd_text, publisher):
        issues.append("高校资讯非招聘岗位")

    if normalized.get("source") == "university_html" and jd_url and _is_list_page_url(jd_url):
        issues.append("链接为列表页非岗位详情")

    if normalized.get("source") == "university_html" and _is_university_as_employer(company, publisher):
        issues.append("高校发布方误作用人单位")

    if (
        normalized.get("source") == "job_aggregator"
        and normalized.get("channel") in ("区域就业平台", "求职聚合")
        and "nowcoder.com/enterprise" not in jd_url
        and not JOB_SIGNAL_RE.search(f"{role} {jd_text}")
        and _looks_like_news_title(f"{role} {jd_text}")
    ):
        issues.append("聚合站活动资讯非岗位")

    if len(role) > 45 and not re.search(r"(工程师|产品|运营|设计|开发|算法|数据|实习|管培|分析师)", role):
        issues.append("标题过长疑似未解析")

    locations = extract_locations(jd_text or normalized.get("location", ""))
    if not normalized.get("city") and not locations and "全国" not in (normalized.get("tags") or []):
        issues.append("未识别工作地")

    if len(jd_text) < 12:
        issues.append("JD 正文过短")

    if issues:
        invalid_hits = {
            "公司名过短",
            "公司名为导航噪声",
            "岗位描述不足",
            "岗位标题无效",
            "JD 正文过短",
            "标题过长疑似未解析",
            "疑似资讯标题非具体岗位",
            "高校资讯非招聘岗位",
            "链接为列表页非岗位详情",
            "聚合站活动资讯非岗位",
            "高校发布方误作用人单位",
        }
        if invalid_hits & set(issues):
            status = "invalid"
        else:
            status = "weak"
    else:
        status = "ok"

    out = normalized
    out["company"] = company
    out["role"] = role[:200]
    out["jd_text"] = jd_text[:2000]
    out["locations"] = locations
    out["job_type"] = infer_job_type(f"{role} {jd_text}")
    if not out.get("published_at"):
        out["published_at"] = extract_published_at(jd_text or role)
    out["validation_status"] = status
    out["validation_issues"] = issues
    out["tags"] = build_tags(out)
    return out
