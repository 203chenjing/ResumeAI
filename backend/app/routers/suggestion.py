"""单条建议调整 router。"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ApiResponse, Suggestion
from app.services.resume_density import assess_density
from app.services.session_store import store
from app.services.suggestion_apply import apply_status_update
from app.services.suggestion_engine import adjust_suggestion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["suggestion"])


class AdjustRequest(BaseModel):
    session_id: str
    suggestion_id: str
    instruction: str


class StatusUpdate(BaseModel):
    session_id: str
    suggestion_id: str
    status: str  # pending | accepted | rejected
    client_id: str = "default"


@router.post("/adjust-suggestion", response_model=ApiResponse)
async def adjust(payload: AdjustRequest):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    if not sess.jd_analysis:
        raise HTTPException(400, "JD 未分析")

    target = next((s for s in sess.suggestions if s.id == payload.suggestion_id), None)
    if not target:
        raise HTTPException(404, "建议不存在")

    updated = await adjust_suggestion(target, payload.instruction, sess.jd_analysis)
    sess.suggestions = [updated if s.id == target.id else s for s in sess.suggestions]
    from app.routers.finalize import mark_finalize_stale

    mark_finalize_stale(sess)
    store.update(sess)

    return ApiResponse(success=True, data={"updated": updated.model_dump()})


@router.post("/update-suggestion-status", response_model=ApiResponse)
async def update_status(payload: StatusUpdate):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")

    if payload.status not in ("pending", "accepted", "rejected", "adjusted"):
        raise HTTPException(400, "非法状态")

    try:
        data = await apply_status_update(sess, payload.suggestion_id, payload.status)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e

    store.update(sess)
    return ApiResponse(
        success=True,
        data={
            "current_markdown": sess.current_resume_md,
            "suggestion": data["suggestion"],
            "finalize_status": sess.finalize_status,
            "match": data["match"],
            "suggestions": [s.model_dump() for s in sess.suggestions],
            "density": data["density"],
        },
    )
