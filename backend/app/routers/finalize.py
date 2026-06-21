"""简历定稿 router。"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.resume_finalizer import finalize_resume
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["finalize"])


class FinalizeRequest(BaseModel):
    session_id: str


def mark_finalize_stale(sess) -> None:
    if sess.finalize_status == "finalized":
        sess.finalize_status = "stale"


@router.post("/finalize-resume", response_model=ApiResponse)
async def finalize_resume_route(payload: FinalizeRequest):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    if not sess.jd_analysis:
        raise HTTPException(400, "请先完成 JD 分析")

    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
    if pending:
        raise HTTPException(400, f"仍有 {len(pending)} 条建议未处理，请先接受或拒绝")

    try:
        result = await finalize_resume(sess)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("finalize failed")
        raise HTTPException(500, f"定稿失败: {e}") from e

    sess.finalized_resume_md = result["markdown"]
    sess.finalize_status = "finalized"
    store.update(sess)

    return ApiResponse(
        success=True,
        data={
            "markdown": sess.finalized_resume_md,
            "regenerated": result["regenerated"],
            "validation": result["validation"],
            "finalize_status": sess.finalize_status,
        },
    )


@router.get("/finalize-status/{session_id}", response_model=ApiResponse)
async def finalize_status(session_id: str):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    return ApiResponse(
        success=True,
        data={
            "finalize_status": sess.finalize_status,
            "finalized_markdown": sess.finalized_resume_md,
            "working_markdown": sess.current_resume_md,
        },
    )
