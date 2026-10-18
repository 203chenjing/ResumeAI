"""一页预算：把「最后才知道」的版面约束变成随时可见的数字。

产品背景：定稿环节才告知「2 页」「12 条编号项」= 沉没成本最高时泼冷水。
这里提供**零渲染成本**的即时指标（改稿页常驻仪表），预检（preflight.py）再用
真实渲染结果校准。
"""
from __future__ import annotations

import math
import re

CHARS_PER_PAGE = 2400  # 实测：~2000 字单页仍有余量，~3050 字溢出到 2 页
EXPERIENCE_ITEM_LIMIT = 5
SKILL_ITEM_LIMIT = 4

_WS = re.compile(r"\s+")
_NUM_LINE = re.compile(r"^\d+\.\s", re.MULTILINE)
_COMPANY_LINE = re.compile(r"\n\*\*[^*]+\*\*\s+[^\n]*\n")
_SKILL_LINE = re.compile(
    r"^\d+\.\s+\*\*(工作技能|数据技能|AI技能|语言能力)\*\*", re.MULTILINE
)


def char_count(markdown: str) -> int:
    """去空白后的字数（与密度评估口径一致）。"""
    return len(_WS.sub("", markdown or ""))


def estimate_pages(chars: int) -> int:
    """按容量估算页数：超出一页容量即向上取整（渲染只会更多，不会更少）。"""
    if chars <= 0:
        return 0
    return max(1, math.ceil(chars / CHARS_PER_PAGE))


def capacity_pct(chars: int) -> int:
    """一页容量占用百分比（用于仪表条，超 100 即预计溢出）。"""
    if chars <= 0:
        return 0
    return min(100, round(chars / CHARS_PER_PAGE * 100))


def experience_items(markdown: str) -> int:
    """实习经历中「单段最多编号项」数（子要点已被降级，不参与计数）。"""
    if "## 实习经历" not in markdown:
        return 0
    block = markdown.split("## 实习经历", 1)[1]
    if "## 相关技能" in block:
        block = block.split("## 相关技能", 1)[0]

    chunks = _COMPANY_LINE.split("\n" + block)
    counts = [len(_NUM_LINE.findall(chunk)) for chunk in chunks[1:]]
    return max(counts) if counts else len(_NUM_LINE.findall(block))


def skill_items(markdown: str) -> int:
    return len(_SKILL_LINE.findall(markdown or ""))


def layout_metrics(markdown: str) -> dict:
    """指标按「规范化后」的正文计算：定稿/导出也走同一套规范化，口径必须一致。"""
    from app.services.resume_list_format import normalize_experience_markdown

    normalized = normalize_experience_markdown(markdown or "")
    chars = char_count(normalized)
    return {
        "char_count": chars,
        "estimated_pages": estimate_pages(chars),
        "capacity_pct": capacity_pct(chars),
        "experience_items": experience_items(normalized),
        "experience_limit": EXPERIENCE_ITEM_LIMIT,
        "skill_items": skill_items(normalized),
        "skill_limit": SKILL_ITEM_LIMIT,
    }
