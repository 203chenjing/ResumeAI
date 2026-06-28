"""简历定稿：校验一页与格式，仅在必要时做最小排版修正。"""
import json
import logging
import tempfile
from pathlib import Path

from app.models.schemas import JDAnalysis, Session
from app.prompts.finalize_resume import build_finalize_prompt
from app.services.llm_client import client
from app.services.photo_context import photo_context_for_session
from app.services.pdf_exporter import validate_resume_markdown
from app.services.resume_emphasis import apply_export_emphasis
from app.services.profile_photo import (
    apply_photo_to_markdown,
    has_session_photo,
    strip_photo_from_markdown,
)

logger = logging.getLogger(__name__)


async def finalize_resume(sess: Session) -> dict:
    """将当前工作稿定稿为可导出版本。

    优先直接校验当前 Markdown；仅在校验失败时调用 LLM 做最小排版修正。
    """
    if not sess.current_resume_md.strip():
        raise ValueError("无简历内容可定稿")

    working_md = sess.current_resume_md
    from app.services.resume_list_format import normalize_experience_markdown

    working_md = normalize_experience_markdown(working_md)
    if sess.profile_photo_ref and has_session_photo(sess.session_id):
        working_md = apply_photo_to_markdown(
            strip_photo_from_markdown(working_md), sess.profile_photo_ref
        )
    validation = validate_resume_markdown(working_md, session_id=sess.session_id)
    regenerated = False

    if not _is_valid(validation):
        working_md, validation, regenerated = await _fix_with_llm(sess, working_md, validation)

    if not _is_valid(validation):
        issues = validation.get("skill_issues", []) + validation.get("layout_issues", [])
        raise ValueError(
            "定稿未通过校验："
            + ("；".join(issues) if issues else "请检查内容长度与格式")
        )

    pre_emphasis_md = working_md
    working_md, emphasis_phrases = await apply_export_emphasis(sess, working_md)
    # 加粗后重新校验页数（通常不变，防止极端情况溢出）
    post_validation = validate_resume_markdown(working_md, session_id=sess.session_id)
    if post_validation.get("page_count", 1) > 1:
        logger.warning("Emphasis caused multi-page PDF, reverting emphasis")
        working_md = pre_emphasis_md
        emphasis_phrases = []
    else:
        validation = {
            **validation,
            **{
                k: post_validation[k]
                for k in ("page_count", "page_passed", "bottom_gap_mm", "layout_issues")
                if k in post_validation
            },
        }

    return {
        "markdown": working_md,
        "regenerated": regenerated,
        "validation": validation,
        "emphasis_phrases": emphasis_phrases,
    }


def _is_valid(validation: dict) -> bool:
    return bool(validation.get("skill_passed") and validation.get("page_passed"))


async def _fix_with_llm(sess: Session, working_md: str, validation: dict) -> tuple[str, dict, bool]:
    issues = list(validation.get("skill_issues", [])) + list(validation.get("layout_issues", []))
    if validation.get("page_count", 0) > 1:
        issues.append(f"PDF 页数为 {validation['page_count']}，必须为 1 页")
    elif validation.get("page_count", 0) == 1 and not validation.get("page_passed"):
        issues.append("单页但底部空白过多，需补充真实内容密度")

    jd_summary = json.dumps(
        sess.jd_analysis.model_dump() if sess.jd_analysis else {},
        ensure_ascii=False,
        indent=2,
    )
    photo_ctx = photo_context_for_session(sess.session_id, sess.profile_photo_ref)
    system, user = build_finalize_prompt(working_md, jd_summary, issues, photo_context=photo_ctx)

    for attempt in range(2):
        logger.info("Finalize layout fix attempt %s", attempt + 1)
        data = await client.chat_text(system, user, temperature=0.2, max_tokens=6000)
        candidate = _extract_markdown(data)
        if sess.profile_photo_ref and has_session_photo(sess.session_id):
            candidate = apply_photo_to_markdown(
                strip_photo_from_markdown(candidate), sess.profile_photo_ref
            )
        next_validation = validate_resume_markdown(candidate, session_id=sess.session_id)
        if _is_valid(next_validation):
            return candidate, next_validation, True
        issues = list(next_validation.get("skill_issues", [])) + list(next_validation.get("layout_issues", []))
        user = (
            user
            + "\n\n上次修正仍未通过：\n"
            + "\n".join(f"- {i}" for i in issues)
            + "\n请继续修正，仍只输出 Markdown。"
        )

    return working_md, validation, False


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
