"""知识库 AI 构建服务。"""
from __future__ import annotations

import json
import logging
import re

from app.prompts.knowledge_base import (
    AUDIT_USER,
    CHAT_SYSTEM,
    EXPAND_STAR_USER,
    INIT_FROM_RESUME_USER,
    KNOWLEDGE_BUILDER_SYSTEM,
)
from app.services.llm_client import client
from app.services.session_store import store

logger = logging.getLogger(__name__)

CHAT_REPLY_RE = re.compile(r"\[CHAT_REPLY\](.*?)\[/CHAT_REPLY\]", re.DOTALL)
KB_UPDATE_RE = re.compile(r"\[KB_UPDATE\](.*?)\[/KB_UPDATE\]", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    m = re.search(r"```(?:markdown)?\s*([\s\S]*?)```", text)
    return m.group(1).strip() if m else text.strip()


def _parse_chat_response(full_text: str) -> dict:
    """解析 Copilot 结构化回复。"""
    reply_match = CHAT_REPLY_RE.search(full_text)
    kb_match = KB_UPDATE_RE.search(full_text)
    reply = reply_match.group(1).strip() if reply_match else full_text.strip()

    updated_md = ""
    if kb_match:
        updated_md = _strip_markdown_fence(kb_match.group(1).strip())
    elif reply_match and "```" in full_text:
        tail = full_text.split("[/CHAT_REPLY]", 1)[-1]
        fenced = _strip_markdown_fence(tail)
        if fenced and fenced != tail.strip() and "##" in fenced:
            updated_md = fenced
            logger.info("Recovered KB update from markdown fence fallback")

    return {"reply": reply, "updated_markdown": updated_md}


def _build_ui_patch(old_md: str, new_md: str, ui_context: dict | None) -> dict:
    if not new_md or new_md.strip() == old_md.strip():
        return {}
    patch: dict = {"focus_panel": "topics", "saved": True}
    selected = (ui_context or {}).get("selected_section_title") or ""
    if selected:
        patch["select_section_title"] = selected
    pending_old = old_md.count("[待补充") + old_md.count("[待确认]")
    pending_new = new_md.count("[待补充") + new_md.count("[待确认]")
    if pending_new > pending_old:
        patch["focus_panel"] = "pending"
    return patch


async def init_from_resume(resume_md: str, existing_kb: str = "") -> str:
    user = INIT_FROM_RESUME_USER.format(
        existing_kb=existing_kb or "（无）",
        resume_md=resume_md[:12000],
    )
    return _strip_markdown_fence(
        await client.chat_text(KNOWLEDGE_BUILDER_SYSTEM, user, max_tokens=4096, temperature=0.2)
    )


async def expand_star(section_title: str, content: str, hint: str = "") -> str:
    user = EXPAND_STAR_USER.format(title=section_title, content=content[:4000], hint=hint or "无")
    return _strip_markdown_fence(
        await client.chat_text(KNOWLEDGE_BUILDER_SYSTEM, user, max_tokens=2048, temperature=0.3)
    )


async def audit_knowledge(kb_md: str) -> dict:
    user = AUDIT_USER.format(content=kb_md[:8000])
    data = await client.chat_json(KNOWLEDGE_BUILDER_SYSTEM, user, max_tokens=1024, temperature=0.2)
    pending_in_text = kb_md.count("[待确认]")
    return {
        "issues": data.get("issues") or [],
        "pending_count": data.get("pending_count", pending_in_text),
        "summary": data.get("summary") or "",
    }


async def chat_knowledge(
    kb_md: str,
    user_message: str,
    history: list[dict] | None = None,
    *,
    ui_context: dict | None = None,
) -> dict:
    ctx_json = json.dumps(ui_context or {}, ensure_ascii=False)
    parts = [
        f"当前知识库（节选）：\n{kb_md[:6000]}",
        f"[界面状态]\n{ctx_json}",
    ]
    for h in history or []:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            parts.append(f"{h['role']}: {h['content'][:2000]}")
    parts.append(f"user: {user_message}")
    bundled = "\n".join(parts)
    raw = await client.chat_text(CHAT_SYSTEM, bundled[:10000], max_tokens=4096, temperature=0.35)
    parsed = _parse_chat_response(raw)
    updated = parsed.get("updated_markdown") or ""
    if updated and len(updated) < 50 and "##" not in updated:
        updated = ""
        parsed["updated_markdown"] = ""
    ui_patch = _build_ui_patch(kb_md, updated, ui_context) if updated else {}
    if updated and parsed.get("reply") and re.search(r"已(写入|更新|生成|整理)", parsed["reply"]):
        logger.info("KB chat produced update (%d chars)", len(updated))
    elif not updated and parsed.get("reply") and re.search(r"已(写入|更新|生成|整理)", parsed["reply"]):
        logger.warning("KB chat claims update but KB_UPDATE empty")
    return {**parsed, "ui_patch": ui_patch}


async def init_from_session(session_id: str, client_id: str = "") -> str:
    sess = store.get(session_id)
    if not sess:
        raise ValueError("会话不存在")
    resume_md = sess.current_resume_md or sess.original_resume_md or ""
    if not resume_md.strip():
        raise ValueError("会话中无简历内容")
    existing = sess.knowledge_base_md or ""
    return await init_from_resume(resume_md, existing)
