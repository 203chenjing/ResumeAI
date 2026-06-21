"""Agent 工具：封装现有业务能力。"""
from __future__ import annotations

import json
import logging

from app.models.schemas import Session
from app.routers.finalize import mark_finalize_stale
from app.routers.knowledge import _sync_photo_into_resume
from app.services.jd_analyzer import analyze_jd
from app.services.knowledge_builder import audit_knowledge, expand_star, init_from_resume
from app.services.match_analyzer import analyze_match
from app.services.resume_density import assess_density
from app.services.resume_finalizer import finalize_resume
from app.services.session_store import store
from app.services.suggestion_apply import apply_suggestion_status
from app.services.session_sync import refresh_match
from app.services.agent_registry import is_risky_tool
from app.services.suggestion_engine import generate_suggestions
from app.services.user_memory import merge_preferences

logger = logging.getLogger(__name__)


def is_risky_action(action: str, action_input: dict | None = None) -> bool:
    return is_risky_tool(action)


async def execute_tool(
    sess: Session,
    action: str,
    action_input: dict,
    *,
    confirmed: bool = False,
    client_id: str = "default",
) -> dict:
    action = (action or "").strip()
    action_input = action_input or {}

    if is_risky_action(action) and not confirmed:
        return {
            "ok": False,
            "requires_confirmation": True,
            "action": action,
            "action_input": action_input,
            "message": _risk_message(action, action_input, sess),
        }

    if action == "get_state":
        return _tool_get_state(sess)
    if action == "save_knowledge_base":
        return _tool_save_knowledge(sess, action_input)
    if action == "init_knowledge_from_resume":
        return await _tool_init_knowledge(sess)
    if action == "expand_star":
        return await _tool_expand_star(sess, action_input)
    if action == "audit_knowledge":
        return await _tool_audit_knowledge(sess)
    if action == "analyze_jd":
        return await _tool_analyze_jd(sess)
    if action == "analyze_match":
        return await _tool_analyze_match(sess)
    if action == "generate_suggestions":
        return await _tool_generate_suggestions(sess)
    if action == "review_suggestions":
        return await _tool_review_suggestions(sess, action_input.get("policy", "accept_safe"))
    if action == "finalize_resume":
        return await _tool_finalize(sess)
    if action == "prepare_export":
        return _tool_prepare_export(sess)
    if action == "update_preferences":
        return _tool_update_preferences(client_id, action_input)
    if action == "finish":
        return {"ok": True, "summary": action_input.get("summary", "")}
    return {"ok": False, "error": f"未知工具: {action}"}


def _tool_update_preferences(client_id: str, action_input: dict) -> dict:
    applied = merge_preferences(client_id, action_input)
    if not applied:
        return {"ok": True, "skipped": True, "reason": "无偏好字段可更新"}
    return {"ok": True, "applied": applied}


def _risk_message(action: str, action_input: dict, sess: Session) -> str:
    if action == "review_suggestions":
        n = len([s for s in sess.suggestions if s.status == "pending"])
        return f"批量处理 {n} 条建议（{action_input.get('policy', 'accept_safe')}）需您确认"
    if action == "finalize_resume":
        return "定稿将锁定当前可导出版本，需您确认"
    if action == "prepare_export":
        return "导出 PDF 需您确认"
    return "该操作需您确认"


def _tool_get_state(sess: Session) -> dict:
    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
    density = assess_density(sess.current_resume_md)
    return {
        "ok": True,
        "status": sess.status,
        "has_jd": bool(sess.jd_analysis),
        "has_match": bool(sess.match_result),
        "suggestion_count": len(sess.suggestions),
        "pending_count": len(pending),
        "finalize_status": sess.finalize_status,
        "resume_chars": len(sess.current_resume_md),
        "density": density,
        "jd_role": sess.jd_analysis.role if sess.jd_analysis else "",
    }


async def _tool_init_knowledge(sess: Session) -> dict:
    resume = (sess.current_resume_md or sess.original_resume_md or "").strip()
    if not resume:
        return {"ok": False, "error": "会话中无简历内容"}
    md = await init_from_resume(resume, sess.knowledge_base_md or "")
    sess.knowledge_base_md = md
    store.update(sess)
    return {
        "ok": True,
        "chars": len(md),
        "pending_markers": md.count("[待确认]"),
    }


async def _tool_expand_star(sess: Session, action_input: dict) -> dict:
    title = (action_input.get("section_title") or "").strip()
    content = (action_input.get("content") or sess.knowledge_base_md or "").strip()
    if not content:
        return {"ok": False, "error": "无段落内容"}
    if not title:
        title = "未命名段落"
    md = await expand_star(title, content, action_input.get("hint") or "")
    return {"ok": True, "markdown": md[:500], "chars": len(md)}


async def _tool_audit_knowledge(sess: Session) -> dict:
    kb = (sess.knowledge_base_md or "").strip()
    if not kb:
        return {"ok": False, "error": "知识库为空"}
    result = await audit_knowledge(kb)
    return {"ok": True, **result}


def _tool_save_knowledge(sess: Session, action_input: dict) -> dict:
    content = (action_input.get("content") or sess.knowledge_base_md or "").strip()
    if not content:
        return {"ok": True, "skipped": True, "reason": "无知识库内容"}
    sess.knowledge_base_md = content
    _sync_photo_into_resume(sess)
    store.update(sess)
    return {"ok": True, "chars": len(content)}


async def _tool_analyze_jd(sess: Session) -> dict:
    if not sess.jd_text.strip():
        return {"ok": False, "error": "会话中无 JD 文本"}
    if sess.jd_analysis:
        return {"ok": True, "skipped": True, "role": sess.jd_analysis.role}
    jd = await analyze_jd(sess.jd_text)
    sess.jd_analysis = jd
    sess.status = "jd_analyzed"
    store.update(sess)
    return {"ok": True, "role": jd.role, "keywords": jd.keywords[:8]}


async def _tool_analyze_match(sess: Session) -> dict:
    if not sess.jd_analysis or not sess.current_resume_md:
        return {"ok": False, "error": "请先完成简历解析与 JD 分析"}
    match = await analyze_match(sess.current_resume_md, sess.jd_analysis)
    sess.match_result = match
    sess.status = "matched"
    store.update(sess)
    return {"ok": True, "overall_score": match.overall_score}


async def _tool_generate_suggestions(sess: Session) -> dict:
    if not sess.match_result:
        return {"ok": False, "error": "请先 analyze_match"}
    suggestions, summary = await generate_suggestions(
        sess.current_resume_md,
        sess.jd_analysis,
        sess.match_result,
        knowledge_base=sess.knowledge_base_md,
        session_id=sess.session_id,
        profile_photo_ref=sess.profile_photo_ref,
    )
    sess.suggestions = suggestions
    sess.status = "suggestions_ready"
    store.update(sess)
    density = assess_density(sess.current_resume_md)
    return {
        "ok": True,
        "count": len(suggestions),
        "summary": summary,
        "density": density,
    }


async def _tool_review_suggestions(sess: Session, policy: str) -> dict:
    pending = [s for s in sess.suggestions if s.status == "pending"]
    if not pending:
        return {"ok": True, "skipped": True, "reason": "无待处理建议"}

    density = assess_density(sess.current_resume_md)
    sparse = density.get("status") == "sparse"
    accepted, rejected = 0, 0

    for s in pending:
        if policy == "reject_all_pending":
            apply_suggestion_status(sess, s, "rejected")
            rejected += 1
            continue
        if policy == "accept_all":
            apply_suggestion_status(sess, s, "accepted")
            accepted += 1
            continue
        if policy == "accept_safe":
            if s.type in ("delete",) or (sparse and s.type == "structure"):
                apply_suggestion_status(sess, s, "rejected")
                rejected += 1
            else:
                apply_suggestion_status(sess, s, "accepted")
                accepted += 1
        else:
            return {"ok": False, "error": f"未知 policy: {policy}"}

    await refresh_match(sess)
    store.update(sess)
    return {
        "ok": True,
        "accepted": accepted,
        "rejected": rejected,
        "resume_chars": len(sess.current_resume_md),
        "density": assess_density(sess.current_resume_md),
    }


async def _tool_finalize(sess: Session) -> dict:
    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
    if pending:
        return {"ok": False, "error": f"仍有 {len(pending)} 条建议未处理"}
    try:
        result = await finalize_resume(sess)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    sess.finalized_resume_md = result["markdown"]
    sess.finalize_status = "finalized"
    store.update(sess)
    return {
        "ok": True,
        "validation": result["validation"],
        "regenerated": result["regenerated"],
    }


def _tool_prepare_export(sess: Session) -> dict:
    if sess.finalize_status != "finalized" or not sess.finalized_resume_md:
        return {"ok": False, "error": "请先定稿再导出"}
    company = sess.jd_analysis.company if sess.jd_analysis and sess.jd_analysis.company else "目标公司"
    name = sess.parsed_resume.header.name if sess.parsed_resume else "候选人"
    role = sess.jd_analysis.role if sess.jd_analysis and sess.jd_analysis.role else "目标岗位"
    filename = f"{company}+{name}+{role}.pdf"
    return {
        "ok": True,
        "export_ready": True,
        "filename": filename,
        "finalize_status": sess.finalize_status,
    }


def build_user_context(sess: Session, goal: str, auto_finalize: bool) -> str:
    return f"""[用户目标]
{goal}

[选项]
auto_finalize: {auto_finalize}

[会话摘要]
session_id: {sess.session_id}
status: {sess.status}
jd_text_length: {len(sess.jd_text)}
knowledge_base_length: {len(sess.knowledge_base_md)}
"""
