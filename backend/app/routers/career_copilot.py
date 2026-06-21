"""求职 Copilot SSE API（LUI + GenUI）。"""
import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.services.career_copilot import stream_career_copilot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["career-copilot"])


class CopilotChatRequest(BaseModel):
    client_id: str = "default"
    message: str = ""
    history: list[dict] = Field(default_factory=list)


@router.post("/career-copilot/chat")
async def career_copilot_chat(payload: CopilotChatRequest):
    async def event_generator():
        try:
            async for event in stream_career_copilot(
                payload.client_id,
                payload.message,
                history=payload.history,
            ):
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
        except Exception as e:
            logger.exception("career copilot error")
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
