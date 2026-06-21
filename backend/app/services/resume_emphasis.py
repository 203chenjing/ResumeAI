"""定稿导出：为量化指标与 JD 强相关短语添加适度加粗。"""
from __future__ import annotations

import json
import logging
import re

from app.models.schemas import JDAnalysis, Session
from app.prompts.export_emphasis import build_export_emphasis_prompt
from app.services.llm_client import client

logger = logging.getLogger(__name__)

MAX_EMPHASIS = 10
MIN_PHRASE_LEN = 3
MAX_PHRASE_LEN = 22
HEADER_LINE_RE = re.compile(r"^\*\*[^*]+\*\*\s+")
METRIC_RE = re.compile(
    r"(?:\d+[%％]|\d+\s*[条个项项次小时天周月年/／]|[约近]\s*\d+)"
)


def _bold_ranges(md: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for m in re.finditer(r"\*\*([^*]+)\*\*", md):
        ranges.append((m.start(), m.end()))
    return ranges


def _inside_bold(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start >= a and end <= b for a, b in ranges)


def _line_at(md: str, index: int) -> str:
    line_start = md.rfind("\n", 0, index) + 1
    line_end = md.find("\n", index)
    if line_end < 0:
        line_end = len(md)
    return md[line_start:line_end]


def _is_protected_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    if HEADER_LINE_RE.match(stripped):
        return True
    if stripped.startswith("手机") or stripped.startswith("求职意向"):
        return True
    if re.match(r"^\d+\.\s+\*\*(工作技能|数据技能|AI技能|语言能力)\*\*：", stripped):
        return True
    return False


def apply_emphasis_phrases(md: str, phrases: list[str]) -> tuple[str, list[str]]:
    """将短语在原文中包裹 **，跳过已加粗与受保护行。"""
    applied: list[str] = []
    out = md
    for raw in phrases:
        phrase = raw.strip()
        if not phrase or len(phrase) < MIN_PHRASE_LEN or len(phrase) > MAX_PHRASE_LEN:
            continue
        if len(applied) >= MAX_EMPHASIS:
            break
        if f"**{phrase}**" in out:
            continue

        ranges = _bold_ranges(out)
        start = 0
        inserted = False
        while True:
            idx = out.find(phrase, start)
            if idx < 0:
                break
            end = idx + len(phrase)
            line = _line_at(out, idx)
            if not _inside_bold(ranges, idx, end) and not _is_protected_line(line):
                out = out[:idx] + f"**{phrase}**" + out[end:]
                applied.append(phrase)
                inserted = True
                break
            start = idx + 1
        if not inserted:
            logger.debug("Skip emphasis phrase (no safe slot): %s", phrase)
    return out, applied


def _rule_based_phrases(md: str, jd: JDAnalysis | None) -> list[str]:
    """LLM 失败时的保守回退：量化短语 + JD 关键词命中。"""
    candidates: list[str] = []

    for line in md.splitlines():
        stripped = line.strip()
        if not re.match(r"^\d+\.", stripped):
            continue
        body = re.sub(r"^\d+\.\s+\*\*[^*]+\*\*：", "", stripped)
        for m in re.finditer(
            r"[^，。；、\s]{2,18}?(?:\d+[%％]|\d+\s*[条个项次小时天周月年]|提升|降低|节省|覆盖)[^，。；]{0,12}",
            body,
        ):
            phrase = m.group(0).strip()
            if MIN_PHRASE_LEN <= len(phrase) <= MAX_PHRASE_LEN:
                candidates.append(phrase)

    if jd:
        keywords = list(jd.keywords or []) + list(jd.core_requirements or [])
        lowered = md.lower()
        for kw in keywords:
            k = kw.strip()
            if len(k) < 2 or len(k) > MAX_PHRASE_LEN:
                continue
            if k in md or k.lower() in lowered:
                if k not in candidates:
                    candidates.append(k)

    deduped: list[str] = []
    seen: set[str] = set()
    for p in candidates:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped[:MAX_EMPHASIS]


def _parse_emphasis_json(text: str) -> list[str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        raw = data.get("emphasis") or data.get("phrases") or []
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            data = json.loads(m.group(0))
            raw = data.get("emphasis") or []
            if isinstance(raw, list):
                return [str(x).strip() for x in raw if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return []


def _jd_summary(jd: JDAnalysis | None) -> str:
    if not jd:
        return "{}"
    return json.dumps(
        {
            "role": jd.role,
            "company": jd.company,
            "keywords": (jd.keywords or [])[:12],
            "core_requirements": (jd.core_requirements or [])[:8],
            "ranking_core": (jd.ranking or {}).get("核心匹配", [])[:6],
        },
        ensure_ascii=False,
        indent=2,
    )


async def apply_export_emphasis(sess: Session, resume_md: str) -> tuple[str, list[str]]:
    """定稿后加粗重点；返回 (新 markdown, 已加粗短语列表)。"""
    if not resume_md.strip():
        return resume_md, []

    existing_body_bolds = len(re.findall(r"^\d+\.\s+\*\*[^*]+\*\*：", resume_md, re.M))
    if existing_body_bolds >= 8 and len(_bold_ranges(resume_md)) > 20:
        logger.info("Skip emphasis: resume already has rich bold structure")
        return resume_md, []

    phrases: list[str] = []
    try:
        system, user = build_export_emphasis_prompt(resume_md, _jd_summary(sess.jd_analysis))
        raw = await client.chat_text(system, user, temperature=0.15, max_tokens=512)
        phrases = _parse_emphasis_json(raw)
    except Exception as exc:
        logger.warning("LLM emphasis failed, using rules: %s", exc)

    if not phrases:
        phrases = _rule_based_phrases(resume_md, sess.jd_analysis)

    # 优先保留含数字的短语
    phrases.sort(key=lambda p: (0 if METRIC_RE.search(p) else 1, len(p)))

    emphasized, applied = apply_emphasis_phrases(resume_md, phrases)
    if applied:
        logger.info("Applied %d emphasis phrases: %s", len(applied), applied[:5])
    return emphasized, applied
