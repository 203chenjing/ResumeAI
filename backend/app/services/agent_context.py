"""动态 Agent 上下文：由会话 + 用户记忆 + 交互历史拼装，非写死策略。"""
from __future__ import annotations

import json

from app.models.schemas import Session
from app.services.agent_registry import tools_prompt_block
from app.services.photo_context import photo_context_for_session
from app.services.resume_density import assess_density
from app.services.user_memory import load_memory


def build_planner_context(
    sess: Session,
    *,
    user_message: str = "",
    goal: str = "",
    client_id: str = "default",
    specialist: str = "coordinator",
    mode: str = "orchestrate",
) -> str:
    """拼装每步 Planner 的用户上下文。"""
    mem = load_memory(client_id)
    prefs = mem.get("preferences", {})
    agent_prefs = getattr(sess, "agent_prefs", None) or {}

    density = assess_density(sess.current_resume_md)
    recent_chat = []
    for m in sess.chat_history[-8:]:
        recent_chat.append({"role": m.role, "content": m.content[:300]})

    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]

    blocks = [
        "==== 用户本轮输入 ====",
        user_message or goal or "（用户未附加文字，请根据会话状态与历史决定下一步）",
        "",
        "==== 用户长期偏好（可经 update_preferences 更新）====",
        json.dumps(prefs, ensure_ascii=False, indent=2),
        "",
        "==== 本会话 Agent 备注（随交互更新）====",
        json.dumps(agent_prefs, ensure_ascii=False, indent=2),
        "",
        "==== 会话快照 ====",
        json.dumps(
            {
                "status": sess.status,
                "finalize_status": sess.finalize_status,
                "jd_role": sess.jd_analysis.role if sess.jd_analysis else None,
                "match_score": sess.match_result.overall_score if sess.match_result else None,
                "suggestions_total": len(sess.suggestions),
                "pending_count": len(pending),
                "resume_chars": len(sess.current_resume_md),
                "density": density,
                "knowledge_chars": len(sess.knowledge_base_md),
                "has_photo": bool(sess.profile_photo_ref),
            },
            ensure_ascii=False,
        ),
        "",
        photo_context_for_session(sess.session_id, sess.profile_photo_ref),
        "",
        "==== 近期对话（最近 8 条）====",
        json.dumps(recent_chat, ensure_ascii=False, indent=2),
        "",
        tools_prompt_block(sess, specialist),
        "",
        f"==== 运行模式 ====\n{mode}（orchestrate=上传页编排；chat=编辑页对话，可选用 mode=chat 改稿）",
    ]
    return "\n".join(blocks)


PLANNER_SYSTEM = """你是 ResumeAI 的动态 Agent 规划器。你不执行写死流水线，而是根据【用户输入】【会话快照】【长期偏好】【近期对话】和【当前可用工具列表】决定下一步。

# 角色（specialist，每步自选）
- analyzer：读懂 JD 与匹配
- writer：建议生成、知识库、偏好学习
- qa：审阅、定稿、导出检查
- coordinator：统筹，可调用任意当前可用工具

# 输出 JSON（每次一条）
{
  "specialist": "analyzer|writer|qa|coordinator",
  "thought": "简短推理，说明为何此时做此步",
  "mode": "tool|confirm|chat|finish|learn",
  "action": "工具名（mode=tool|confirm 时必填）",
  "action_input": {},
  "message": "mode=confirm 时给用户的确认文案",
  "summary": "mode=finish 时的汇报",
  "preference_updates": {"writing_style":"...", "review_policy":"...", "notes":"...", "recent_intent":"..."}
}

# mode 说明
- tool：执行非高风险工具，或已获用户确认后的操作
- confirm：高风险工具（review_suggestions/finalize_resume/prepare_export）必须先征求用户确认，不可直接执行
- chat：编辑模式下，改稿/闲聊/生成 NEW_SUGGESTIONS，不调用工具（仅 mode=chat 时）
- finish：目标已达成或应交给用户手动操作
- learn：仅更新 preference_updates，不调用工具，用于记住用户习惯

# 原则
- 不要重复已完成且工具列表中已消失的步骤
- review_suggestions 的 policy 参考用户偏好 review_policy，无则根据密度与 pending 内容自定
- 不要编造工具名；只能从【当前可用工具】中选择
- 用户明确拒绝或取消时 mode=finish
- 每轮只推进一个有意义步骤，避免一次连调多个工具
"""
