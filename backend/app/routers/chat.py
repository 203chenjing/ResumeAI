"""聊天 router (SSE 流式)。"""
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatMessage
from app.routers.finalize import mark_finalize_stale
from app.services.chat_engine import stream_chat
from app.services.photo_context import photo_context_for_session
from app.services.session_sync import upsert_suggestions
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("/chat")
async def chat(payload: ChatRequest):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    if not sess.jd_analysis:
        raise HTTPException(400, "请先完成 JD 分析")

    user_msg = ChatMessage(role="user", content=payload.message)
    sess.chat_history.append(user_msg)

    async def event_generator():
        full_reply = ""
        new_sugs: list[dict] = []
        try:
            photo_ctx = photo_context_for_session(sess.session_id, sess.profile_photo_ref)
            async for event in stream_chat(
                user_message=payload.message,
                chat_history=sess.chat_history[:-1],
                current_resume=sess.current_resume_md,
                current_suggestions=sess.suggestions,
                jd=sess.jd_analysis,
                photo_context=photo_ctx,
            ):
                if event["type"] == "text":
                    full_reply += event["content"]
                    yield {"event": "message", "data": json.dumps({"type": "text", "content": event["content"]}, ensure_ascii=False)}
                elif event["type"] == "reply_end":
                    yield {"event": "message", "data": json.dumps({"type": "reply_end"}, ensure_ascii=False)}
                elif event["type"] == "done":
                    new_sugs = event.get("new_suggestions", [])
                    full_reply = event.get("reply_text") or full_reply
                    if new_sugs:
                        upsert_suggestions(sess, new_sugs)
                        mark_finalize_stale(sess)
                    yield {
                        "event": "message",
                        "data": json.dumps(
                            {
                                "type": "done",
                                "reply": full_reply,
                                "new_suggestions": new_sugs,
                                "suggestions": [s.model_dump() for s in sess.suggestions],
                                "current_markdown": sess.current_resume_md,
                                "match": sess.match_result.model_dump() if sess.match_result else None,
                                "finalize_status": sess.finalize_status,
                            },
                            ensure_ascii=False,
                        ),
                    }
        except Exception as e:
            logger.exception("chat stream error")
            yield {"event": "message", "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)}
            return

        # 持久化（建议已在 done 时 upsert）
        ai_msg = ChatMessage(role="assistant", content=full_reply)
        sess.chat_history.append(ai_msg)
        store.update(sess)

    return EventSourceResponse(event_generator())
