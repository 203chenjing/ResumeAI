"""将建议 original_text 锚定到简历 Markdown 中的可定位片段。"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.models.schemas import Suggestion

_NUM_LINE = re.compile(r"^\d+\.\s*.+")
_NUM_PREFIX = re.compile(r"^\d+\s*[.、．]\s*")
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub("", text or "").lower()


def _strip_number(text: str) -> str:
    """去掉列表编号：建议里的 `1.` 可能和简历当前编号不一致。"""
    return _NUM_PREFIX.sub("", (text or "").strip())


def _extract_title(text: str) -> str:
    t = text.strip()
    m = re.match(r"^\d+\.\s*(?:\*\*([^*]+)\*\*|([^：:]+))[：:]", t)
    if m:
        return (m.group(1) or m.group(2) or "").strip()
    for sep in ("：", ":"):
        if sep in t:
            head = t.split(sep, 1)[0]
            head = re.sub(r"^\d+\.\s*", "", head).strip("* ").strip()
            if 2 <= len(head) <= 40:
                return head
    return ""


def _experience_numbered_lines(resume_md: str) -> list[str]:
    if "## 实习经历" not in resume_md:
        return []
    block = resume_md.split("## 实习经历", 1)[1]
    if "## 相关技能" in block:
        block = block.split("## 相关技能", 1)[0]
    lines: list[str] = []
    for line in block.split("\n"):
        s = line.strip()
        if _NUM_LINE.match(s):
            lines.append(s)
    return lines


def _similar(a: str, b: str, *, threshold: float = 0.55) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def find_line_range(resume_md: str, text: str) -> list[int]:
    needle = (text or "").strip()
    if not needle:
        return [0, 0]
    lines = resume_md.split("\n")
    for i, line in enumerate(lines, 1):
        if needle in line or line.strip() == needle:
            return [i, i]

    # 编号漂移：建议文本常带旧编号，比对时忽略行首 `N.`
    nn = _norm(_strip_number(needle))
    if nn:
        for i, line in enumerate(lines, 1):
            nl = _norm(_strip_number(line))
            if not nl:
                continue
            if nn == nl or (len(nl) >= 8 and (nn in nl or nl in nn)):
                return [i, i]
    return [0, 0]


def anchor_original_text(
    resume_md: str,
    original_text: str,
) -> tuple[str, list[int]]:
    """返回 (可精确匹配的原文片段, line_range)。"""
    ot = (original_text or "").strip()
    if not ot or not resume_md.strip():
        return ot, [0, 0]

    if ot in resume_md:
        return ot, find_line_range(resume_md, ot)

    title = _extract_title(ot)
    numbered = _experience_numbered_lines(resume_md)

    for line in numbered:
        if ot in line or line in ot:
            return line, find_line_range(resume_md, line)
        if _similar(ot, line):
            return line, find_line_range(resume_md, line)
        if title and title in line:
            return line, find_line_range(resume_md, line)

    for line in resume_md.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ot in s or s in ot:
            return s, find_line_range(resume_md, s)
        if title and title in s and len(s) > 20:
            return s, find_line_range(resume_md, s)

    return ot, [0, 0]


def anchor_suggestion(suggestion: Suggestion, resume_md: str) -> Suggestion:
    if not suggestion.original_text or suggestion.section == "header":
        return suggestion
    anchored, line_range = anchor_original_text(resume_md, suggestion.original_text)
    updates: dict = {}
    if anchored and anchored != suggestion.original_text:
        updates["original_text"] = anchored
    if line_range != suggestion.line_range:
        updates["line_range"] = line_range
    if not updates:
        return suggestion
    return suggestion.model_copy(update=updates)


def anchor_suggestions(suggestions: list[Suggestion], resume_md: str) -> list[Suggestion]:
    return [anchor_suggestion(s, resume_md) for s in suggestions]
