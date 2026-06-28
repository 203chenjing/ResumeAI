"""简历可编辑条目目录：从 Markdown 解析出行号索引，供 LLM 定位（非意图规则）。"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

_NUM_LINE = re.compile(r"^(\d+)\.\s*(.+)$")
_SECTION = re.compile(r"^##\s+(.+)$")
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}")


def _norm(text: str) -> str:
    return _WS.sub("", text or "").lower()


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text or ""))


def _token_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if inter == 0:
        return 0.0
    return inter / min(len(ta), len(tb))


def _similar(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.95
    return SequenceMatcher(None, na, nb).ratio()


def build_edit_catalog(resume_md: str) -> list[dict[str, Any]]:
    """枚举简历中可逐条修改的 numbered item 及关键表头行。"""
    if not resume_md.strip():
        return []

    items: list[dict[str, Any]] = []
    section = "header"
    company = ""

    for line_no, raw in enumerate(resume_md.split("\n"), 1):
        stripped = raw.strip()
        if not stripped:
            continue

        sec = _SECTION.match(stripped)
        if sec:
            section = sec.group(1).strip()
            company = ""
            continue

        if section == "实习经历" and stripped.startswith("**") and not _NUM_LINE.match(stripped):
            company = stripped.replace("**", "").split("  ")[0].strip()
            items.append(
                {
                    "line": line_no,
                    "section": section,
                    "kind": "experience_header",
                    "company": company,
                    "text": stripped,
                    "preview": stripped[:72],
                }
            )
            continue

        num = _NUM_LINE.match(stripped)
        if num and section in ("实习经历", "相关技能", "教育经历"):
            items.append(
                {
                    "line": line_no,
                    "section": section,
                    "kind": "numbered_item",
                    "index": int(num.group(1)),
                    "company": company or None,
                    "text": stripped,
                    "preview": stripped[:96] + ("…" if len(stripped) > 96 else ""),
                }
            )

    return items


def catalog_entry_by_line(catalog: list[dict[str, Any]], line: int) -> dict[str, Any] | None:
    for item in catalog:
        if item.get("line") == line:
            return item
    return None


def catalog_for_prompt(catalog: list[dict[str, Any]], *, max_items: int = 40) -> list[dict[str, Any]]:
    """压缩目录供 LLM 选择行号（含足够上下文以理解多种指代方式）。"""
    rows: list[dict[str, Any]] = []
    for item in catalog[:max_items]:
        if item.get("kind") != "numbered_item":
            continue
        text = item.get("text") or ""
        rows.append(
            {
                "line": item["line"],
                "section": item["section"],
                "index": item.get("index"),
                "company": item.get("company"),
                "text": text[:320] + ("…" if len(text) > 320 else ""),
                "preview": item.get("preview") or text[:96],
            }
        )
    return rows


def numbered_items(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in catalog if c.get("kind") == "numbered_item"]


def _substring_boost(query: str, text: str) -> float:
    qn, tn = _norm(query), _norm(text)
    if not qn or not tn:
        return 0.0
    best = 0.0
    for n in range(2, 6):
        for i in range(len(qn) - n + 1):
            gram = qn[i : i + n]
            if gram in tn:
                best = max(best, n / 5.0)
    return min(best, 0.55)


def _score_line(query: str, item: dict[str, Any], user_message: str) -> float:
    text = item.get("text") or ""
    preview = item.get("preview") or text
    company = str(item.get("company") or "")
    idx = str(item.get("index") or "")
    q = query.strip()
    um = user_message.strip()
    base = max(
        _similar(q, text),
        _similar(q, preview),
        _similar(um, text) * 0.85,
        _token_overlap(q, text),
        _token_overlap(q, preview),
        _token_overlap(um, text) * 0.9,
        _substring_boost(q, text),
        _substring_boost(um, text),
    )
    if company:
        base = max(base, _similar(q, company) * 0.9, _similar(um, company) * 0.75)
    if idx and idx in q:
        base += 0.05
    return min(base, 1.0)


def match_catalog_lines_semantic(
    catalog: list[dict[str, Any]],
    *,
    queries: list[str],
    user_message: str,
    min_score: float = 0.22,
    max_per_query: int = 2,
) -> list[dict[str, Any]]:
    """将自然语言指代对齐到目录行（文本相似度，不用固定关键词表）。"""
    items = numbered_items(catalog)
    if not items or not queries:
        return []

    picked: list[dict[str, Any]] = []
    seen_lines: set[int] = set()

    for query in queries:
        if not query.strip():
            continue
        scored = sorted(
            ((_score_line(query, it, user_message), it) for it in items),
            key=lambda x: x[0],
            reverse=True,
        )
        added = 0
        for score, it in scored:
            if score < min_score:
                break
            line = int(it["line"])
            if line in seen_lines:
                continue
            seen_lines.add(line)
            picked.append({"line": line, "intent": query.strip(), "score": round(score, 3)})
            added += 1
            if added >= max_per_query:
                break
    return picked
