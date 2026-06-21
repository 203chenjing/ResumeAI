"""知识库 AI Copilot API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.knowledge_builder import audit_knowledge, chat_knowledge, expand_star, init_from_session
from app.services.session_store import store
from app.services.user_memory import load_memory, save_memory

router = APIRouter(prefix="/api", tags=["knowledge-agent"])


class InitFromResumeBody(BaseModel):
    client_id: str = "default"
    session_id: str = ""


class ExpandStarBody(BaseModel):
    section_title: str
    content: str
    hint: str = ""


class AuditBody(BaseModel):
    content: str


class KnowledgeChatBody(BaseModel):
    client_id: str = "default"
    content: str
    message: str
    history: list[dict] = Field(default_factory=list)
    session_id: str = ""
    ui_context: dict | None = None


def _persist_knowledge(client_id: str, session_id: str, markdown: str) -> None:
    mem = load_memory(client_id)
    mem["knowledge_base_md"] = markdown
    save_memory(client_id, mem)
    if session_id:
        sess = store.get(session_id)
        if sess:
            sess.knowledge_base_md = markdown
            store.update(sess)


@router.post("/knowledge-agent/init-from-resume", response_model=ApiResponse)
async def post_init_from_resume(body: InitFromResumeBody):
    if not body.session_id:
        raise HTTPException(400, "需要 session_id")
    try:
        markdown = await init_from_session(body.session_id, body.client_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    sess = store.get(body.session_id)
    if sess:
        sess.knowledge_base_md = markdown
        store.update(sess)
    mem = load_memory(body.client_id)
    mem["knowledge_base_md"] = markdown
    save_memory(body.client_id, mem)
    return ApiResponse(success=True, data={"markdown": markdown})


@router.post("/knowledge-agent/expand-star", response_model=ApiResponse)
async def post_expand_star(body: ExpandStarBody):
    if not body.content.strip():
        raise HTTPException(400, "content 不能为空")
    md = await expand_star(body.section_title, body.content, body.hint)
    return ApiResponse(success=True, data={"markdown": md})


@router.post("/knowledge-agent/audit", response_model=ApiResponse)
async def post_audit(body: AuditBody):
    if not body.content.strip():
        raise HTTPException(400, "content 不能为空")
    result = await audit_knowledge(body.content)
    return ApiResponse(success=True, data=result)


@router.post("/knowledge-agent/chat", response_model=ApiResponse)
async def post_chat(body: KnowledgeChatBody):
    if not body.message.strip():
        raise HTTPException(400, "message 不能为空")
    result = await chat_knowledge(
        body.content,
        body.message,
        body.history,
        ui_context=body.ui_context,
    )
    updated = (result.get("updated_markdown") or "").strip()
    saved = False
    if updated and updated != body.content.strip():
        _persist_knowledge(body.client_id, body.session_id, updated)
        saved = True
    return ApiResponse(
        success=True,
        data={
            "reply": result.get("reply") or "",
            "updated_markdown": updated or None,
            "saved": saved,
            "ui_patch": result.get("ui_patch") or {},
        },
    )
