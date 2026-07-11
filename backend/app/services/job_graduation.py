"""届别（26/27 届）提取、标签与过滤。"""
from __future__ import annotations

import re

GRADUATION_TAG_PREFIX = "届别:"

GRADUATION_DUAL_RE = re.compile(r"26\s*/\s*27届|26/27届")
GRADUATION_27_RE = re.compile(r"(?<![\d/])27届|2027届")
GRADUATION_26_RE = re.compile(r"(?<![\d/])26届|2026届")

# github 0voice 等仓库的章节标题，不是公司名
GITHUB_CATEGORY_COMPANIES = frozenset(
    {
        "后端岗位",
        "算法岗位",
        "测试开发",
        "游戏",
        "AI大模型",
        "硬件/芯片/通信相关技术岗",
        "前端开发",
        "运维/安全",
        "数据分析",
        "机器学习",
        "产品",
        "运营",
        "设计岗",
        "大厂岗",
        "中厂",
        "独角兽",
        "国企",
        "央企",
        "外企",
        "优质潜力企业",
        "开发岗",
        "算法岗",
        "测试",
        "测试/运维/安全岗",
        "硬件岗",
        "金融岗",
        "实习篇",
        "校招篇",
        "26春招岗",
        "26秋招岗",
        "春招岗",
        "秋招岗",
    }
)


def extract_graduation_classes(text: str) -> list[str]:
    """从岗位文本提取届别，返回 ['26'] / ['27'] / ['26','27']。"""
    t = text or ""
    if GRADUATION_DUAL_RE.search(t):
        return ["26", "27"]
    found: set[str] = set()
    if GRADUATION_27_RE.search(t):
        found.add("27")
    if GRADUATION_26_RE.search(t):
        found.add("26")
    return sorted(found)


def graduation_classes_from_tags(tags: list) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        s = str(t).strip()
        if not s.startswith(GRADUATION_TAG_PREFIX):
            continue
        label = s[len(GRADUATION_TAG_PREFIX) :].replace("届", "").strip()
        if label in ("26", "27") and label not in out:
            out.append(label)
    return sorted(out)


def get_graduation_classes(job: dict) -> list[str]:
    from_tags = graduation_classes_from_tags(job.get("tags") or [])
    if from_tags:
        return from_tags
    if job.get("graduation_classes"):
        return list(job["graduation_classes"])
    blob = " ".join(
        [
            str(job.get("company") or ""),
            str(job.get("role") or ""),
            str(job.get("jd_text") or ""),
            " ".join(str(x) for x in (job.get("tags") or [])),
        ]
    )
    return extract_graduation_classes(blob)


def graduation_display(job: dict) -> str:
    classes = get_graduation_classes(job)
    if not classes:
        return ""
    if classes == ["26", "27"]:
        return "26/27届"
    return f"{classes[-1]}届"


def enrich_graduation(job: dict) -> dict:
    """写入 graduation_classes 与 届别:* tags。"""
    out = dict(job)
    blob = " ".join(
        [
            str(out.get("company") or ""),
            str(out.get("role") or ""),
            str(out.get("jd_text") or ""),
        ]
    )
    classes = extract_graduation_classes(blob)
    if not classes:
        classes = graduation_classes_from_tags(out.get("tags") or [])

    tags = [t for t in (out.get("tags") or []) if not str(t).startswith(GRADUATION_TAG_PREFIX)]
    for c in classes:
        tag = f"{GRADUATION_TAG_PREFIX}{c}届"
        if tag not in tags:
            tags.append(tag)
    out["tags"] = tags[:14]
    out["graduation_classes"] = classes
    return out


def matches_graduation_filter(
    job: dict,
    target_class: str,
    *,
    include_unlabeled: bool = False,
) -> bool:
    """target_class: '27' | '26' | ''(不过滤)。"""
    target = (target_class or "").replace("届", "").strip()
    if not target:
        return True

    classes = get_graduation_classes(job)
    if not classes:
        return include_unlabeled

    if target in classes:
        return True

    # 查 27 届时，纯 26 届（无 27）排除
    if target == "27" and classes == ["26"]:
        return False
    if target == "26" and classes == ["27"]:
        return False

    return include_unlabeled


def is_github_category_company(company: str) -> bool:
    c = (company or "").strip()
    if not c:
        return False
    if c in GITHUB_CATEGORY_COMPANIES:
        return True
    if c.endswith("岗位") or c.endswith("技术岗"):
        return True
    return False
