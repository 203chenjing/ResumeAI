"""修改建议生成与调整服务。"""
import json
import logging
import re
import uuid

from app.models.schemas import JDAnalysis, MatchResult, Suggestion
from app.prompts.suggestions import build_suggestion_prompt
from app.prompts.adjust import build_adjust_prompt
from app.services.llm_client import client
from app.services.suggestion_anchor import anchor_suggestions
from app.services.resume_list_format import ensure_experience_item_format

logger = logging.getLogger(__name__)


_NOOP_REASON_RE = re.compile(
    r"无需(?:再)?修改|无须(?:再)?修改|不需要修改|不用(?:再)?改|无需改动|不用改动"
)

_STIFF_TAIL_RE = re.compile(
    r"(?:[，,；;]|^)\s*"
    r"(?:体现|突出|展现|彰显|具备|具有(?:较强)?的?|展示(?:出)?)"
    r"[^。；]{2,48}$"
)

_EMBED_KEYWORD_REASON_RE = re.compile(r"嵌入\s*JD\s*关键词|关键词.*嵌入")


def _added_tail(original: str, suggested: str) -> str:
    o = (original or "").strip()
    s = (suggested or "").strip()
    if not o or not s.startswith(o):
        return ""
    return s[len(o) :].strip()


def _is_stiff_keyword_suggestion(suggestion: Suggestion) -> bool:
    """过滤句尾硬贴 JD 软技能/素质词的生硬 keyword/wording 建议。"""
    if suggestion.type not in ("keyword", "wording"):
        return False

    tail = _added_tail(suggestion.original_text, suggestion.suggested_text)
    if tail and _STIFF_TAIL_RE.search(tail):
        return True

    orig_n = _normalize_suggestion_text(suggestion.original_text)
    sugg_n = _normalize_suggestion_text(suggestion.suggested_text)
    if orig_n and sugg_n.startswith(orig_n) and len(sugg_n) - len(orig_n) <= 40:
        if _EMBED_KEYWORD_REASON_RE.search(suggestion.reason or ""):
            return True
        if tail and len(tail) <= 24 and any(k in tail for k in ("体现", "突出", "具备", "具有")):
            return True

    return False


def _filter_stiff_keyword_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    filtered: list[Suggestion] = []
    for s in suggestions:
        if _is_stiff_keyword_suggestion(s):
            logger.info("Drop stiff keyword suggestion: %s", s.id)
            continue
        filtered.append(s)
    return filtered


def _normalize_suggestion_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip("。；;，,、. ")


def _is_noop_suggestion(suggestion: Suggestion) -> bool:
    """过滤模型误把“无需修改”当成待处理建议的 no-op 条目。"""
    original = _normalize_suggestion_text(suggestion.original_text)
    suggested = _normalize_suggestion_text(suggestion.suggested_text)
    return (bool(original) and original == suggested) or bool(_NOOP_REASON_RE.search(suggestion.reason or ""))


def _filter_noop_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    filtered: list[Suggestion] = []
    for s in suggestions:
        if _is_noop_suggestion(s):
            logger.info("Drop noop suggestion: %s", s.id)
            continue
        filtered.append(s)
    return filtered


def _normalize_experience_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    """经历区建议统一为 `N. **小标题**：…` 分点格式。"""
    out: list[Suggestion] = []
    for s in suggestions:
        if s.section != "experience" or not s.suggested_text:
            out.append(s)
            continue
        normalized = ensure_experience_item_format(
            s.suggested_text, reference=s.original_text or s.suggested_text
        )
        if normalized == s.suggested_text:
            out.append(s)
            continue
        out.append(s.model_copy(update={"suggested_text": normalized}))
    return out


def _filter_suggestions_by_density(suggestions: list[Suggestion], resume_md: str) -> list[Suggestion]:
    """按一页密度规则过滤危险建议（过多 delete）。"""
    density = assess_density(resume_md)
    filtered: list[Suggestion] = []
    delete_count = 0
    for s in suggestions:
        if s.type == "delete":
            if density["status"] == "sparse":
                logger.info("Drop delete suggestion in sparse resume: %s", s.id)
                continue
            delete_count += 1
            if delete_count > 2:
                logger.info("Drop excess delete suggestion: %s", s.id)
                continue
        filtered.append(s)
    return filtered


async def generate_suggestions(
    resume_md: str,
    jd: JDAnalysis,
    match: MatchResult,
    knowledge_base: str = "",
    *,
    session_id: str = "",
    profile_photo_ref: str = "",
) -> tuple[list[Suggestion], dict]:
    from app.services.photo_context import photo_context_for_session

    photo_section = ""
    if session_id:
        photo_section = photo_context_for_session(session_id, profile_photo_ref)

    system, user = build_suggestion_prompt(
        resume_md,
        json.dumps(jd.model_dump(), ensure_ascii=False, indent=2),
        json.dumps(match.model_dump(), ensure_ascii=False, indent=2),
        knowledge_base,
        photo_section=photo_section,
    )
    data = await client.chat_json(system, user, temperature=0.4, max_tokens=6000)
    raw_list = data.get("suggestions", [])

    suggestions: list[Suggestion] = []
    for i, item in enumerate(raw_list):
        if not item.get("id"):
            item["id"] = f"sug_{uuid.uuid4().hex[:8]}"
        item.setdefault("status", "pending")
        item.setdefault("line_range", [0, 0])
        item.setdefault("jd_match_points", [])
        try:
            suggestions.append(Suggestion(**item))
        except Exception as e:
            logger.warning(f"Skip invalid suggestion: {e}, item={item}")

    suggestions = _filter_noop_suggestions(suggestions)
    suggestions = _filter_stiff_keyword_suggestions(suggestions)
    suggestions = _normalize_experience_suggestions(suggestions)
    suggestions = anchor_suggestions(suggestions, resume_md)
    suggestions = _filter_suggestions_by_density(suggestions, resume_md)
    summary = _compute_summary(suggestions)
    return suggestions, summary


def _compute_summary(suggestions: list[Suggestion]) -> dict:
    by_type: dict[str, int] = {}
    by_section: dict[str, int] = {}
    for s in suggestions:
        by_type[s.type] = by_type.get(s.type, 0) + 1
        by_section[s.section] = by_section.get(s.section, 0) + 1
    return {"total": len(suggestions), "by_type": by_type, "by_section": by_section}


async def adjust_suggestion(
    suggestion: Suggestion,
    instruction: str,
    jd: JDAnalysis,
) -> Suggestion:
    system, user = build_adjust_prompt(
        suggestion_json=json.dumps(suggestion.model_dump(), ensure_ascii=False, indent=2),
        instruction=instruction,
        jd_summary=json.dumps(jd.model_dump(), ensure_ascii=False, indent=2),
    )
    data = await client.chat_json(system, user, temperature=0.4)
    data["id"] = suggestion.id  # 保持 id
    data["status"] = "adjusted"
    adj = Suggestion(**data)
    if adj.section == "experience" and adj.suggested_text:
        adj = adj.model_copy(
            update={
                "suggested_text": ensure_experience_item_format(
                    adj.suggested_text, reference=adj.original_text or adj.suggested_text
                )
            }
        )
    return adj
