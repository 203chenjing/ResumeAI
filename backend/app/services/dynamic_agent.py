"""动态 Agent 核心：Planner 根据会话、记忆与用户输入选择 specialist + tool，无写死流水线。"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from app.models.schemas import Session
from app.services.agent_context import PLANNER_SYSTEM, build_planner_context
from app.services.agent_registry import available_tools, is_risky_tool
from app.services.agent_tools import execute_tool
from app.services.chat_engine import stream_chat
from app.services.llm_client import client
from app.services.photo_context import photo_context_for_session
from app.services.resume_density import assess_density
from app.services.session_store import store
from app.services.session_sync import build_session_payload
from app.services.user_memory import load_memory, merge_preferences

logger = logging.getLogger(__name__)

MAX_ORCHESTRATE_STEPS = 14


def _default_goal(client_id: str) -> str:
    prefs = load_memory(client_id).get("preferences", {})
    if prefs.get("recent_intent"):
        return str(prefs["recent_intent"])
    return "根据当前 JD、简历与我的偏好，推进分析与建议生成；高风险步骤先征求确认"


def _apply_preference_updates(sess: Session, client_id: str, updates: dict | None) -> dict:
    if not updates:
        return {}
    filtered = merge_preferences(client_id, updates)
    agent_prefs = dict(getattr(sess, "agent_prefs", None) or {})
    agent_prefs.update({k: v for k, v in updates.items() if v})
    sess.agent_prefs = agent_prefs
    store.update(sess)
    return filtered


def _review_policy(client_id: str) -> str:
    prefs = load_memory(client_id).get("preferences", {})
    if prefs.get("review_policy"):
        return str(prefs["review_policy"])
    if prefs.get("prefer_accept_safe", True):
        return "accept_safe"
    return "accept_all"


def _confirm_message(action: str, action_input: dict, sess: Session, client_id: str = "default") -> str:
    if action == "review_suggestions":
        n = len([s for s in sess.suggestions if s.status == "pending"])
        policy = action_input.get("policy") or _review_policy(client_id)
        return f"将批量处理 {n} 条待审建议（策略：{policy}），是否继续？"
    if action == "finalize_resume":
        return "确认定稿？定稿后预览与导出 PDF 将一致。"
    if action == "prepare_export":
        return "确认导出当前定稿 PDF？"
    return "确认执行该操作？"


def _after_action_reply(action: str, result: dict) -> str:
    if not result.get("ok"):
        return result.get("error") or result.get("message") or "操作未完成"
    if action == "review_suggestions":
        return f"已处理建议：接受 {result.get('accepted', 0)} 条，拒绝 {result.get('rejected', 0)} 条。"
    if action == "finalize_resume":
        return "定稿成功，可在左侧查看定稿预览，或说「导出」下载 PDF。"
    if action == "prepare_export":
        return "已准备好导出，正在触发下载…"
    if action == "get_state":
        n = result.get("pending_count", 0)
        if n > 0:
            return f"左侧「修改建议」面板有 {n} 条待处理，请查看待处理筛选。"
        return "当前没有待处理建议。"
    if action == "update_preferences":
        return "已更新您的长期偏好。"
    return result.get("summary") or "操作完成。"


def _session_payload(sess: Session) -> dict:
    return build_session_payload(sess)


def _done_event(sess: Session, summary: str, *, extra: dict | None = None) -> dict:
    ev = {"type": "done", "summary": summary, **_session_payload(sess)}
    if extra:
        ev.update(extra)
    return ev


async def _plan_step(
    sess: Session,
    *,
    user_message: str,
    goal: str,
    client_id: str,
    specialist: str,
    mode: str,
    step_history: list[dict],
) -> dict:
    ctx = build_planner_context(
        sess,
        user_message=user_message,
        goal=goal,
        client_id=client_id,
        specialist=specialist,
        mode=mode,
    )
    if step_history:
        ctx += "\n\n==== 本轮已执行步骤 ====\n" + json.dumps(step_history[-6:], ensure_ascii=False)

    if not client.api_key or client.api_key == "DEMO_KEY":
        return _fallback_decision(sess, client_id, specialist, mode)

    try:
        return await client.chat_messages_json(
            [{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": ctx}],
            temperature=0.2,
            max_tokens=900,
        )
    except Exception:
        logger.exception("planner failed, using state-driven fallback")
        return _fallback_decision(sess, client_id, specialist, mode)


def _fallback_decision(sess: Session, client_id: str, specialist: str, mode: str) -> dict:
    tools = available_tools(sess, specialist)
    names = [t["name"] for t in tools if not t["name"].startswith("_")]
    if not names:
        return {
            "mode": "finish",
            "specialist": specialist,
            "summary": "当前无更多自动步骤，请在编辑页继续",
        }
    action = names[0]
    action_input: dict = {}
    if action == "review_suggestions":
        action_input["policy"] = _review_policy(client_id)
    if action == "save_knowledge_base":
        action_input = {}
    if is_risky_tool(action):
        return {
            "mode": "confirm",
            "specialist": specialist,
            "action": action,
            "action_input": action_input,
            "message": _confirm_message(action, action_input, sess, client_id),
            "thought": f"降级模式：{action} 需确认",
        }
    if mode == "chat" and action in ("analyze_jd", "analyze_match", "generate_suggestions"):
        return {"mode": "chat", "specialist": specialist, "thought": "使用对话模式协助改稿"}
    return {
        "mode": "tool",
        "specialist": specialist,
        "action": action,
        "action_input": action_input,
        "thought": f"降级模式：执行 {action}",
    }


async def stream_dynamic_agent(
    sess: Session,
    *,
    user_message: str = "",
    goal: str = "",
    client_id: str = "default",
    mode: str = "orchestrate",
    auto_finalize: bool = False,
    confirmed_action: dict | None = None,
    max_steps: int = MAX_ORCHESTRATE_STEPS,
    ui_context: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """统一动态 Agent 流。orchestrate=上传页多步编排；chat=编辑页单轮对话。"""
    effective_goal = (goal or user_message or _default_goal(client_id)).strip()

    if confirmed_action:
        action = confirmed_action.get("action", "")
        action_input = confirmed_action.get("action_input") or {}
        agent_label = "edit" if mode == "chat" else "coordinator"
        yield {"type": "tool_call", "action": action, "input": action_input, "agent": agent_label}
        result = await execute_tool(sess, action, action_input, confirmed=True, client_id=client_id)
        store.update(sess)
        yield {"type": "tool_result", "action": action, "result": result, "agent": agent_label}
        if action == "prepare_export" and result.get("export_ready"):
            yield {"type": "export_ready", "filename": result.get("filename")}
        reply = _after_action_reply(action, result)
        if mode == "chat":
            yield {"type": "done", "reply": reply, "new_suggestions": [], **_session_payload(sess)}
        else:
            yield _done_event(sess, reply)
        return

    specialist = "coordinator"
    step_history: list[dict] = []
    loop_limit = 1 if mode == "chat" else max_steps

    if mode == "orchestrate":
        yield {
            "type": "agent_phase",
            "agent": "coordinator",
            "content": "动态 Agent 已启动，将根据会话状态逐步规划…",
        }

    for step in range(loop_limit):
        decision = await _plan_step(
            sess,
            user_message=user_message if step == 0 else "",
            goal=effective_goal,
            client_id=client_id,
            specialist=specialist,
            mode=mode,
            step_history=step_history,
        )

        specialist = (decision.get("specialist") or specialist).strip() or "coordinator"
        planner_mode = (decision.get("mode") or "tool").strip()
        thought = (decision.get("thought") or "").strip()

        pref_updates = decision.get("preference_updates")
        if pref_updates:
            applied = _apply_preference_updates(sess, client_id, pref_updates)
            if applied:
                yield {"type": "customization_update", "updates": applied, "agent": specialist}

        if thought:
            yield {"type": "thought", "content": thought, "agent": specialist, "step": step + 1}
        if specialist != "coordinator" and mode == "orchestrate":
            yield {"type": "agent_phase", "agent": specialist, "content": f"{specialist} 接管本步"}

        if planner_mode == "learn":
            if mode == "chat":
                planner_mode = "chat"
            else:
                continue

        if planner_mode == "finish":
            summary = decision.get("summary") or thought or "任务已完成"
            if mode == "chat":
                yield {"type": "done", "reply": summary, "new_suggestions": [], **_session_payload(sess)}
            else:
                yield _done_event(sess, summary)
            return

        if planner_mode == "chat" and mode == "chat":
            photo_ctx = photo_context_for_session(sess.session_id, sess.profile_photo_ref)
            from app.services.user_memory import memory_context_for_prompt

            mem_ctx = memory_context_for_prompt(client_id)
            async for event in stream_chat(
                user_message=user_message,
                chat_history=sess.chat_history,
                current_resume=sess.current_resume_md,
                current_suggestions=sess.suggestions,
                jd=sess.jd_analysis,
                photo_context=f"{photo_ctx}\n\n{mem_ctx}",
                ui_context=ui_context,
            ):
                if event["type"] in ("text", "reply_end"):
                    yield event
                elif event["type"] == "done":
                    yield {
                        "type": "done",
                        "reply": event.get("reply_text", ""),
                        "new_suggestions": event.get("new_suggestions", []),
                        **_session_payload(sess),
                    }
            return

        action = (decision.get("action") or "").strip()
        action_input = dict(decision.get("action_input") or {})

        if planner_mode == "confirm" or (planner_mode == "tool" and is_risky_tool(action)):
            if action == "review_suggestions" and not action_input.get("policy"):
                action_input["policy"] = _review_policy(client_id)
            yield {
                "type": "confirmation_required",
                "action": action,
                "input": action_input,
                "message": decision.get("message") or _confirm_message(action, action_input, sess, client_id),
                "agent": specialist,
            }
            return

        if planner_mode != "tool" or not action:
            if mode == "chat":
                planner_mode = "chat"
                photo_ctx = photo_context_for_session(sess.session_id, sess.profile_photo_ref)
                from app.services.user_memory import memory_context_for_prompt

                mem_ctx = memory_context_for_prompt(client_id)
                async for event in stream_chat(
                    user_message=user_message,
                    chat_history=sess.chat_history,
                    current_resume=sess.current_resume_md,
                    current_suggestions=sess.suggestions,
                    jd=sess.jd_analysis,
                    photo_context=f"{photo_ctx}\n\n{mem_ctx}",
                    ui_context=ui_context,
                ):
                    if event["type"] in ("text", "reply_end"):
                        yield event
                    elif event["type"] == "done":
                        yield {
                            "type": "done",
                            "reply": event.get("reply_text", ""),
                            "new_suggestions": event.get("new_suggestions", []),
                            **_session_payload(sess),
                        }
                return
            continue

        if action == "finish":
            summary = action_input.get("summary") or thought or "完成"
            yield _done_event(sess, summary)
            return

        yield {"type": "tool_call", "action": action, "input": action_input, "agent": specialist, "step": step + 1}
        result = await execute_tool(sess, action, action_input, confirmed=True, client_id=client_id)
        store.update(sess)
        yield {"type": "tool_result", "action": action, "result": result, "agent": specialist, "step": step + 1}

        step_history.append({"action": action, "ok": result.get("ok"), "skipped": result.get("skipped")})

        if action == "prepare_export" and result.get("export_ready"):
            yield {"type": "export_ready", "filename": result.get("filename")}

        if not result.get("ok") and not result.get("skipped"):
            err = result.get("error", "未知错误")
            if mode == "chat":
                yield {"type": "done", "reply": err, "new_suggestions": [], **_session_payload(sess)}
            else:
                yield _done_event(sess, f"步骤 {action} 失败：{err}")
            return

        if mode == "chat":
            yield {
                "type": "done",
                "reply": decision.get("reply_hint") or _after_action_reply(action, result),
                "new_suggestions": [],
                **_session_payload(sess),
            }
            return

        if action == "finalize_resume" and result.get("ok"):
            yield _done_event(sess, "已完成定稿，可导出 PDF")
            return

        if auto_finalize and action == "review_suggestions" and result.get("ok"):
            pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
            if not pending:
                fin = await execute_tool(sess, "finalize_resume", {}, confirmed=True, client_id=client_id)
                store.update(sess)
                yield {"type": "tool_call", "action": "finalize_resume", "input": {}, "agent": "qa"}
                yield {"type": "tool_result", "action": "finalize_resume", "result": fin, "agent": "qa"}
                if fin.get("ok"):
                    yield _done_event(sess, "审阅完成并已自动定稿")
                    return

        essential_done = (
            sess.jd_analysis
            and sess.match_result
            and sess.suggestions
            and not any(s.status == "pending" for s in sess.suggestions)
        )
        if essential_done and not auto_finalize and action == "review_suggestions":
            yield _done_event(sess, "分析、建议与安全审阅已完成，请在编辑页确认后定稿")
            return

    summary = "已达到规划步数上限，请继续在编辑页操作"
    if mode == "chat":
        yield {"type": "done", "reply": summary, "new_suggestions": [], **_session_payload(sess)}
    else:
        yield _done_event(sess, summary)
