"""面试准备 + 模拟面试 API。"""
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ApiResponse
from app.services.application_store import list_applications
from app.services.interview_prep import build_prep_pack
from app.services.mock_interview import stream_mock_interview
from app.services.user_memory import load_memory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["interview"])


class PrepBody(BaseModel):
    client_id: str = "default"
    application_id: str = ""
    jd_text: str = ""
    company: str = ""
    role: str = ""


class MockInterviewBody(BaseModel):
    client_id: str = "default"
    application_id: str = ""
    round_type: str = "hr"
    jd_text: str = ""
    company: str = ""
    role: str = ""
    user_answer: str = ""
    turn: int = 0


@router.post("/interview/prep", response_model=ApiResponse)
async def post_prep(body: PrepBody):
    company = body.company
    role = body.role
    jd_text = body.jd_text

    if body.application_id:
        apps = list_applications(body.client_id)
        app = next((a for a in apps if a.get("id") == body.application_id), None)
        if not app:
            raise HTTPException(404, "申请不存在")
        company = app.get("company", company)
        role = app.get("role", role)
        jd_text = app.get("jd_text", jd_text)

    mem = load_memory(body.client_id)
    pack = build_prep_pack(
        jd_text=jd_text,
        company=company,
        role=role,
        knowledge_md=mem.get("knowledge_base_md", ""),
    )
    return ApiResponse(success=True, data=pack)


@router.post("/interview/mock")
async def post_mock(body: MockInterviewBody):
    company = body.company
    role = body.role
    jd_text = body.jd_text

    if body.application_id:
        apps = list_applications(body.client_id)
        app = next((a for a in apps if a.get("id") == body.application_id), None)
        if app:
            company = app.get("company", company)
            role = app.get("role", role)
            jd_text = app.get("jd_text", jd_text)

    async def event_generator():
        try:
            async for event in stream_mock_interview(
                round_type=body.round_type,
                jd_text=jd_text,
                company=company,
                role=role,
                user_answer=body.user_answer,
                turn=body.turn,
                client_id=body.client_id,
            ):
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
        except Exception as e:
            logger.exception("mock interview error")
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
