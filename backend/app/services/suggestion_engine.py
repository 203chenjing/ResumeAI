"""修改建议生成与调整服务。"""
import json
import logging
import uuid

from app.models.schemas import JDAnalysis, MatchResult, Suggestion
from app.prompts.suggestions import build_suggestion_prompt
from app.prompts.adjust import build_adjust_prompt
from app.services.llm_client import client
from app.services.resume_density import assess_density

logger = logging.getLogger(__name__)


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

    suggestions = _filter_suggestions_by_density(suggestions, resume_md)
    summary = data.get("summary", _compute_summary(suggestions))
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
    return Suggestion(**data)
