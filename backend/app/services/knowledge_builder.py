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

CHAT_REPLY_RE = re.compile(r"\[CHAT_REPLY\](.*?)\[/CHAT_REPLY\]", re.DOTALL | re.IGNORECASE)
KB_UPDATE_RE = re.compile(r"\[KB_UPDATE\](.*?)\[/KB_UPDATE\]", re.DOTALL | re.IGNORECASE)
KB_UPDATE_OPEN_RE = re.compile(r"\[KB_UPDATE\](.*)", re.DOTALL | re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)")


def _strip_markdown_fence(text: str) -> str:
    m = re.search(r"```(?:markdown)?\s*([\s\S]*?)```", text)
    return m.group(1).strip() if m else text.strip()


def _extract_headings(md: str) -> list[str]:
    titles: list[str] = []
    for line in md.split("\n"):
        m = HEADING_RE.match(line.strip())
        if m:
            titles.append(m.group(2).strip())
    return titles


def _find_changed_heading(old_md: str, new_md: str, ui_context: dict | None) -> str:
    old_heads = set(_extract_headings(old_md))
    new_heads = _extract_headings(new_md)
    added = [t for t in new_heads if t not in old_heads]
    project_keys = ("项目", "实习", "公司", "岗位", "经历")
    for title in reversed(added):
        if any(k in title for k in project_keys):
            return title
    if added:
        return added[-1]
    selected = (ui_context or {}).get("selected_section_title") or ""
    return selected


def _merge_kb_update(full_kb: str, update: str) -> str:
    """将片段更新合并进完整知识库，或接受完整文档替换。"""
    update = update.strip()
    if not update:
        return full_kb
    if update.startswith("# 简历知识库") or "## 使用规则" in update[:600]:
        return update
    if len(update) > max(len(full_kb) * 0.45, 400) and "##" in update:
        return update
    marker = "## 实习 / 项目素材"
    alt_marker = "## 实习/项目素材"
    for m in (marker, alt_marker):
        if m in full_kb and m not in update and update.startswith("###"):
            idx = full_kb.find(m)
            next_h2 = full_kb.find("\n## ", idx + len(m))
            insert_at = next_h2 if next_h2 > 0 else len(full_kb)
            head = full_kb[:insert_at].rstrip()
            tail = full_kb[insert_at:].lstrip("\n")
            return f"{head}\n\n{update}\n\n{tail}".strip() + "\n"
    return f"{full_kb.rstrip()}\n\n{update}\n"


def _parse_chat_response(full_text: str) -> dict:
    """解析 Copilot 结构化回复。"""
    reply_match = CHAT_REPLY_RE.search(full_text)
    kb_match = KB_UPDATE_RE.search(full_text)
    reply = reply_match.group(1).strip() if reply_match else full_text.strip()

    updated_md = ""
    if kb_match:
        updated_md = _strip_markdown_fence(kb_match.group(1).strip())
    else:
        open_match = KB_UPDATE_OPEN_RE.search(full_text)
        if open_match:
            candidate = _strip_markdown_fence(open_match.group(1).strip())
            if "##" in candidate or "###" in candidate:
                updated_md = candidate
                logger.info("Recovered KB update from unclosed KB_UPDATE tag")

    if not updated_md and reply_match and "```" in full_text:
        tail = full_text.split("[/CHAT_REPLY]", 1)[-1]
        fenced = _strip_markdown_fence(tail)
        if fenced and fenced != tail.strip() and "##" in fenced:
            updated_md = fenced
            logger.info("Recovered KB update from markdown fence fallback")

    if not updated_md and reply_match:
        fenced_reply = _strip_markdown_fence(reply)
        if fenced_reply.startswith("#") and "##" in fenced_reply:
            updated_md = fenced_reply
            reply = "已更新知识库内容，请在左侧查看。"
            logger.info("Recovered KB update from fenced content in CHAT_REPLY")

    return {"reply": reply, "updated_markdown": updated_md}


def _build_ui_patch(old_md: str, new_md: str, ui_context: dict | None) -> dict:
    if not new_md or new_md.strip() == old_md.strip():
        return {}
    patch: dict = {"focus_panel": "topics", "saved": True}
    changed = _find_changed_heading(old_md, new_md, ui_context)
    if changed:
        patch["select_section_title"] = changed
    pending_old = old_md.count("[待补充") + old_md.count("[待确认]")
    pending_new = new_md.count("[待补充") + new_md.count("[待确认]")
    if pending_new > pending_old and not changed:
        patch["focus_panel"] = "pending"
    return patch


def _bundle_chat_prompt(
    kb_md: str,
    user_message: str,
    history: list[dict] | None,
    ui_context: dict | None,
    *,
    max_chars: int = 12000,
) -> str:
    """组装对话 prompt，确保最新 user 消息不被截断。"""
    ctx_json = json.dumps(ui_context or {}, ensure_ascii=False)
    user_part = f"user: {user_message}"
    overhead = len(user_part) + len(ctx_json) + 120

    history_parts: list[str] = []
    for h in (history or [])[-4:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            history_parts.append(f"{h['role']}: {h['content'][:1000]}")

    history_len = sum(len(p) + 1 for p in history_parts)
    kb_budget = max(2500, max_chars - overhead - history_len)
    kb_excerpt = kb_md if len(kb_md) <= kb_budget else kb_md[:kb_budget] + "\n…（后续内容已截断）"

    parts = [
        f"当前知识库：\n{kb_excerpt}",
        f"[界面状态]\n{ctx_json}",
        *history_parts,
        user_part,
    ]
    bundled = "\n".join(parts)
    if len(bundled) > max_chars:
        trim = len(bundled) - max_chars
        kb_excerpt = kb_excerpt[: max(2000, len(kb_excerpt) - trim)]
        parts[0] = f"当前知识库：\n{kb_excerpt}"
        bundled = "\n".join(parts)
    return bundled


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
    bundled = _bundle_chat_prompt(kb_md, user_message, history, ui_context)
    raw = await client.chat_text(CHAT_SYSTEM, bundled, max_tokens=8192, temperature=0.35)
    parsed = _parse_chat_response(raw)
    updated = parsed.get("updated_markdown") or ""
    if updated:
        updated = _merge_kb_update(kb_md, updated)
        parsed["updated_markdown"] = updated
    if updated and len(updated) < 50 and "##" not in updated:
        updated = ""
        parsed["updated_markdown"] = ""
    ui_patch = _build_ui_patch(kb_md, updated, ui_context) if updated else {}
    if updated and parsed.get("reply") and re.search(r"已(写入|更新|生成|整理|添加)", parsed["reply"]):
        logger.info("KB chat produced update (%d chars)", len(updated))
    elif not updated and parsed.get("reply") and re.search(r"已(写入|更新|生成|整理|添加)", parsed["reply"]):
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
