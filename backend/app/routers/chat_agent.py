"""编辑页 Agent 对话 router。"""
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatMessage
from app.routers.finalize import mark_finalize_stale
from app.services.edit_chat_agent import stream_edit_chat
from app.services.session_sync import (
    build_session_payload,
    build_ui_patch_for_pending,
    build_ui_patch_for_suggestions,
    upsert_suggestions,
)
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat-agent"])


class EditChatRequest(BaseModel):
    session_id: str
    message: str = ""
    client_id: str = Field(default="default", max_length=64)
    confirmed_action: dict | None = None
    ui_context: dict | None = None


@router.post("/chat/agent")
async def edit_chat_agent(payload: EditChatRequest):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    if not sess.jd_analysis:
        raise HTTPException(400, "请先完成 JD 分析")

    if payload.message and not payload.confirmed_action:
        sess.chat_history.append(ChatMessage(role="user", content=payload.message))

    async def event_generator():
        full_reply = ""
        pending_before = len(
            [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
        )
        try:
            async for event in stream_edit_chat(
                sess,
                payload.message,
                client_id=payload.client_id,
                confirmed_action=payload.confirmed_action,
                ui_context=payload.ui_context,
            ):
                etype = event.get("type")
                if etype == "text":
                    full_reply += event.get("content", "")
                if etype == "done":
                    full_reply = event.get("reply") or full_reply
                    new_sugs = event.get("new_suggestions", [])
                    if new_sugs:
                        upsert_suggestions(sess, new_sugs)
                        mark_finalize_stale(sess)
                    # 始终以服务端最新会话为准，避免 new_suggestions 与 session 不同步
                    event = {**event, **build_session_payload(sess)}
                    if new_sugs:
                        patch = build_ui_patch_for_suggestions(new_sugs)
                        if patch:
                            event["ui_patch"] = patch
                    elif not event.get("ui_patch"):
                        pending_now = [
                            s for s in sess.suggestions if s.status in ("pending", "adjusted")
                        ]
                        if len(pending_now) > pending_before:
                            patch = build_ui_patch_for_suggestions(
                                [s.model_dump() for s in pending_now]
                            )
                            if patch:
                                event["ui_patch"] = patch
                        if not event.get("ui_patch"):
                            patch = build_ui_patch_for_pending(
                                sess,
                                user_message=payload.message,
                                reply=event.get("reply") or full_reply,
                            )
                            if patch:
                                event["ui_patch"] = patch
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
        except Exception as e:
            logger.exception("edit chat agent error")
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False),
            }
            return

        if full_reply:
            sess.chat_history.append(ChatMessage(role="assistant", content=full_reply))
        store.update(sess)

    return EventSourceResponse(event_generator())
