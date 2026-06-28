"""指哪打哪改稿：LLM 意图解析 → 行号定位 → 结构化建议生成。"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncGenerator

from app.models.schemas import ChatMessage, JDAnalysis, Session, Suggestion
from app.prompts.role_lens import build_role_lens_section
from app.prompts.targeted_edit import (
    build_generate_targeted_prompt,
    build_resolve_edit_plan_prompt,
)
from app.services.chat_engine import stream_chat
from app.services.edit_catalog import (
    build_edit_catalog,
    catalog_entry_by_line,
    catalog_for_prompt,
    match_catalog_lines_semantic,
)
from app.services.llm_client import client
from app.services.suggestion_anchor import anchor_suggestions
from app.services.suggestion_engine import (
    _filter_noop_suggestions,
    _filter_stiff_keyword_suggestions,
    _normalize_experience_suggestions,
)

logger = logging.getLogger(__name__)

RISKY_TOOLS = frozenset(
    {
        "build_resume_from_knowledge",
        "review_suggestions",
        "finalize_resume",
        "prepare_export",
    }
)


def _recent_chat(history: list[ChatMessage], limit: int = 6) -> list[dict]:
    return [{"role": m.role, "content": m.content[:400]} for m in history[-limit:]]


def _merge_targets(
    catalog: list[dict],
    *,
    line_targets: list[dict],
    semantic_queries: list[str],
    user_message: str,
    valid_lines: set[int],
) -> list[dict]:
    merged: dict[int, dict] = {}
    for t in line_targets:
        if not isinstance(t, dict):
            continue
        try:
            line = int(t.get("line"))
        except (TypeError, ValueError):
            continue
        if line in valid_lines:
            merged[line] = {"line": line, "intent": str(t.get("intent") or "").strip()}

    for hit in match_catalog_lines_semantic(
        catalog, queries=semantic_queries, user_message=user_message
    ):
        line = hit["line"]
        if line not in merged:
            merged[line] = {"line": line, "intent": hit.get("intent") or ""}
        elif not merged[line].get("intent"):
            merged[line]["intent"] = hit.get("intent") or ""

    return list(merged.values())


async def resolve_edit_plan(
    user_message: str,
    resume_md: str,
    jd: JDAnalysis | None,
    *,
    chat_history: list[ChatMessage] | None = None,
    ui_context: dict | None = None,
) -> dict[str, Any]:
    catalog = build_edit_catalog(resume_md)
    catalog_rows = catalog_for_prompt(catalog)
    valid_lines = {int(item["line"]) for item in catalog_rows}
    jd_json = json.dumps(jd.model_dump() if jd else {}, ensure_ascii=False, indent=2)
    role_lens = build_role_lens_section(jd.model_dump() if jd else {})
    system, user = build_resolve_edit_plan_prompt(
        user_message=user_message,
        catalog_json=json.dumps(catalog_rows, ensure_ascii=False, indent=2),
        jd_json=jd_json,
        ui_context_json=json.dumps(ui_context or {}, ensure_ascii=False),
        recent_chat_json=json.dumps(_recent_chat(chat_history or []), ensure_ascii=False),
        role_lens_section=role_lens,
    )
    try:
        plan = await client.chat_json(system, user, temperature=0.15, max_tokens=1400)
    except Exception:
        logger.exception("resolve_edit_plan failed")
        return {"action": "conversational", "reply": ""}

    action = (plan.get("action") or "conversational").strip()
    line_targets = plan.get("targets") if isinstance(plan.get("targets"), list) else []
    semantic_queries: list[str] = []
    for key in ("referents", "target_hints", "semantic_targets"):
        raw = plan.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                semantic_queries.append(item.strip())
            elif isinstance(item, dict):
                desc = str(item.get("describe") or item.get("hint") or item.get("intent") or "").strip()
                if desc:
                    semantic_queries.append(desc)

    cleaned = _merge_targets(
        catalog,
        line_targets=line_targets,
        semantic_queries=semantic_queries,
        user_message=user_message,
        valid_lines=valid_lines,
    )
    plan["targets"] = cleaned

    if action == "targeted_edit" and not cleaned:
        plan["action"] = "clarify"
        plan["message"] = plan.get("message") or (
            "我还不能确定您要改目录里的哪几条。请用任意说法指明段落"
            "（例如公司名、第几条、项目/模块名称），或粘贴要替换的原文片段。"
        )
    return plan


async def generate_targeted_suggestions(
    plan: dict[str, Any],
    resume_md: str,
    jd: JDAnalysis | None,
) -> list[Suggestion]:
    catalog = build_edit_catalog(resume_md)
    targets = plan.get("targets") or []
    entries = []
    for t in targets:
        entry = catalog_entry_by_line(catalog, t["line"])
        if entry and entry.get("kind") == "numbered_item":
            entries.append({**entry, "intent": t.get("intent", "")})
    if not entries:
        return []

    jd_json = json.dumps(jd.model_dump() if jd else {}, ensure_ascii=False, indent=2)
    role_lens = build_role_lens_section(jd.model_dump() if jd else {})
    system, user = build_generate_targeted_prompt(
        targets_json=json.dumps(targets, ensure_ascii=False, indent=2),
        entries_json=json.dumps(entries, ensure_ascii=False, indent=2),
        edit_brief=str(plan.get("edit_brief") or ""),
        jd_json=jd_json,
        role_lens_section=role_lens,
    )
    try:
        data = await client.chat_json(system, user, temperature=0.35, max_tokens=4500)
    except Exception:
        logger.exception("generate_targeted_suggestions failed")
        return []

    raw_list = data.get("suggestions") if isinstance(data, dict) else []
    if not isinstance(raw_list, list):
        return []

    suggestions: list[Suggestion] = []
    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue
        if not item.get("id"):
            item["id"] = f"sug_t_{uuid.uuid4().hex[:8]}"
        item.setdefault("status", "pending")
        item.setdefault("jd_match_points", [])
        orig = str(item.get("original_text") or "")
        line = 0
        for e in entries:
            et = e.get("text") or ""
            if et and (et in orig or orig in et or orig == et):
                line = e["line"]
                if not orig:
                    item["original_text"] = et
                break
        if not line and entries:
            line = entries[min(i, len(entries) - 1)]["line"]
        item["line_range"] = [line, line]
        try:
            suggestions.append(Suggestion(**item))
        except Exception as e:
            logger.warning("Skip targeted suggestion: %s", e)

    suggestions = _filter_noop_suggestions(suggestions)
    suggestions = _filter_stiff_keyword_suggestions(suggestions)
    suggestions = _normalize_experience_suggestions(suggestions)
    return anchor_suggestions(suggestions, resume_md)


async def run_targeted_edit(
    user_message: str,
    sess: Session,
    *,
    ui_context: dict | None = None,
) -> dict[str, Any]:
    """单次改稿：返回 action、reply、建议、可选 tool 确认信息。"""
    plan = await resolve_edit_plan(
        user_message,
        sess.current_resume_md,
        sess.jd_analysis,
        chat_history=sess.chat_history,
        ui_context=ui_context,
    )
    action = plan.get("action") or "conversational"

    if action == "clarify":
        return {"action": action, "reply": plan.get("message") or "请具体说明要改哪一段经历。", "suggestions": []}

    if action == "confirm_tool":
        tool = (plan.get("tool") or "").strip()
        return {
            "action": action,
            "reply": plan.get("message") or "该操作需要您确认后执行。",
            "suggestions": [],
            "tool": tool,
            "tool_input": plan.get("tool_input") or {},
            "requires_confirmation": tool in RISKY_TOOLS or tool in ("save_knowledge_base",),
        }

    if action == "targeted_edit":
        suggestions = await generate_targeted_suggestions(plan, sess.current_resume_md, sess.jd_analysis)
        if suggestions:
            n = len(suggestions)
            lines = ", ".join(str(t["line"]) for t in plan.get("targets", [])[:5])
            reply = plan.get("reply") or (
                f"已定位第 {lines} 行等 {n} 处修改，中间栏「待处理」可逐条确认；点击建议可在左侧高亮原文。"
            )
            return {"action": action, "reply": reply, "suggestions": suggestions, "plan": plan}
        return {
            "action": "clarify",
            "reply": "已理解改稿方向，但未能生成可定位的建议，请换一种说法或指明目录中的条目。",
            "suggestions": [],
        }

    return {"action": "conversational", "reply": plan.get("reply") or "", "suggestions": []}


async def stream_targeted_edit(
    user_message: str,
    sess: Session,
    *,
    ui_context: dict | None = None,
    photo_context: str = "",
) -> AsyncGenerator[dict, None]:
    """编辑页智能改稿流：先理解+定位，再生成建议或转对话/确认。"""
    if not (user_message or "").strip():
        yield {"type": "done", "reply_text": "请告诉我您想改哪一段。", "new_suggestions": []}
        return

    yield {"type": "thought", "content": "正在理解改稿意图并定位简历条目…", "agent": "writer"}

    result = await run_targeted_edit(user_message, sess, ui_context=ui_context)
    action = result.get("action")

    if action == "confirm_tool" and result.get("requires_confirmation"):
        yield {
            "type": "confirmation_required",
            "action": result.get("tool"),
            "input": result.get("tool_input") or {},
            "message": result.get("reply") or "确认执行该操作？",
            "agent": "writer",
        }
        return

    if action == "targeted_edit" and result.get("suggestions"):
        targets = (result.get("plan") or {}).get("targets") or []
        preview = "、".join(f"第{t['line']}行" for t in targets[:4])
        yield {
            "type": "thought",
            "content": f"已定位 {preview}，正在生成逐条修改建议…",
            "agent": "writer",
        }
        reply = result.get("reply") or ""
        if reply:
            yield {"type": "text", "content": reply}
        sug_dicts = [s.model_dump() for s in result["suggestions"]]
        yield {
            "type": "done",
            "reply_text": reply,
            "new_suggestions": sug_dicts,
            "ui_patch": {
                "filter": "pending",
                "highlight_ids": [s["id"] for s in sug_dicts if s.get("id")],
                "focus_panel": "suggestions",
            },
        }
        return

    if action == "clarify":
        yield {"type": "done", "reply_text": result.get("reply") or "", "new_suggestions": []}
        return

    async for event in stream_chat(
        user_message=user_message,
        chat_history=sess.chat_history,
        current_resume=sess.current_resume_md,
        current_suggestions=sess.suggestions,
        jd=sess.jd_analysis,
        photo_context=photo_context,
        ui_context=ui_context,
    ):
        yield event
