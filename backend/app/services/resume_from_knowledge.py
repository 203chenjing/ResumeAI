"""从知识库生成针对 JD 的工作稿简历。"""
from __future__ import annotations

import json
import logging
import re

from app.models.schemas import Session
from app.prompts.resume_from_knowledge import build_resume_from_knowledge_prompt
from app.routers.finalize import mark_finalize_stale
from app.services.llm_client import client
from app.services.match_analyzer import analyze_match
from app.services.profile_photo import apply_photo_to_markdown, has_session_photo, strip_photo_from_markdown
from app.services.resume_density import assess_density
from app.services.session_store import store
from app.services.suggestion_engine import generate_suggestions
from app.services.user_memory import load_memory

logger = logging.getLogger(__name__)


def _extract_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _resolve_knowledge(sess: Session, kb_override: str, client_id: str) -> str:
    kb = (kb_override or "").strip() or (sess.knowledge_base_md or "").strip()
    if not kb:
        kb = (load_memory(client_id).get("knowledge_base_md") or "").strip()
    return kb


async def build_resume_from_knowledge(
    sess: Session,
    *,
    knowledge_base: str = "",
    client_id: str = "default",
    regenerate_suggestions: bool = True,
) -> dict:
    """用知识库 + JD 生成新的 current_resume_md，可选重新生成建议。"""
    kb = _resolve_knowledge(sess, knowledge_base, client_id)
    if not kb:
        raise ValueError("知识库为空，请先在知识库页整理经历素材")
    if not sess.jd_analysis:
        raise ValueError("请先完成岗位分析")

    working = sess.current_resume_md or sess.original_resume_md or ""
    jd_json = json.dumps(sess.jd_analysis.model_dump(), ensure_ascii=False, indent=2)
    system, user = build_resume_from_knowledge_prompt(kb, working, jd_json)

    raw = await client.chat_text(system, user, temperature=0.25, max_tokens=6000)
    markdown = _extract_markdown(raw)
    if not markdown.strip() or "#" not in markdown:
        raise ValueError("未能从知识库生成有效简历，请检查知识库内容后重试")

    if sess.profile_photo_ref and has_session_photo(sess.session_id):
        markdown = apply_photo_to_markdown(
            strip_photo_from_markdown(markdown), sess.profile_photo_ref
        )
    elif "![个人照片]" in working and "![个人照片]" not in markdown:
        photo_line = re.search(r"!\[个人照片\]\([^)]+\)", working)
        if photo_line:
            markdown = markdown.replace(
                "## 教育经历",
                f"{photo_line.group(0)}\n\n## 教育经历",
                1,
            )

    sess.knowledge_base_md = kb
    sess.current_resume_md = markdown
    mark_finalize_stale(sess)
    sess.status = "matched" if sess.match_result else "jd_analyzed"

    suggestions_count = 0
    if regenerate_suggestions:
        sess.match_result = await analyze_match(sess.current_resume_md, sess.jd_analysis)
        suggestions, _ = await generate_suggestions(
            sess.current_resume_md,
            sess.jd_analysis,
            sess.match_result,
            knowledge_base=kb,
            session_id=sess.session_id,
            profile_photo_ref=sess.profile_photo_ref,
        )
        sess.suggestions = suggestions
        sess.status = "suggestions_ready"
        suggestions_count = len(suggestions)

    store.update(sess)
    density = assess_density(sess.current_resume_md)
    logger.info(
        "Built resume from KB (%d chars, %d suggestions)",
        len(markdown),
        suggestions_count,
    )
    return {
        "markdown": sess.current_resume_md,
        "knowledge_base_md": kb,
        "suggestions_count": suggestions_count,
        "match": sess.match_result.model_dump() if sess.match_result else None,
        "suggestions": [s.model_dump() for s in sess.suggestions],
        "density": density,
        "finalize_status": sess.finalize_status,
    }
