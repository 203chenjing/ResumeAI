"""简历定稿 router：预检 → 定稿（可显式例外）→ 导出。"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.layout_budget import layout_metrics
from app.services.preflight import run_preflight
from app.services.resume_compressor import compress_to_page
from app.services.resume_finalizer import FinalizeBlocked, finalize_resume
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["finalize"])


class FinalizeRequest(BaseModel):
    session_id: str
    force: bool = False  # 用户显式确认「不是一页也导出」


class SessionRequest(BaseModel):
    session_id: str


def mark_finalize_stale(sess) -> None:
    if sess.finalize_status == "finalized":
        sess.finalize_status = "stale"


def _get_session(session_id: str):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    return sess


@router.get("/layout-metrics/{session_id}", response_model=ApiResponse)
async def get_layout_metrics(session_id: str):
    """零渲染成本的即时容量指标（改稿页常驻仪表用）。"""
    sess = _get_session(session_id)
    return ApiResponse(
        success=True,
        data=layout_metrics(sess.current_resume_md or ""),
    )


@router.post("/preflight", response_model=ApiResponse)
async def preflight_route(payload: SessionRequest):
    """真实渲染一次的预检：页数 / 格式 / 留白，问题带可执行动作。"""
    sess = _get_session(payload.session_id)
    return ApiResponse(success=True, data=run_preflight(sess))


@router.post("/compress-to-page", response_model=ApiResponse)
async def compress_route(payload: SessionRequest):
    """只压缩最长的几条 bullet（不重写整篇），可撤销。"""
    sess = _get_session(payload.session_id)
    result = await compress_to_page(sess)
    store.update(sess)
    return ApiResponse(success=True, data=result)


@router.post("/undo-compression", response_model=ApiResponse)
async def undo_compress_route(payload: SessionRequest):
    sess = _get_session(payload.session_id)
    if not sess.pre_compress_md:
        raise HTTPException(400, "没有可撤销的压缩记录")
    sess.current_resume_md = sess.pre_compress_md
    sess.pre_compress_md = ""
    store.update(sess)
    return ApiResponse(
        success=True,
        data={"markdown": sess.current_resume_md, "metrics": layout_metrics(sess.current_resume_md)},
    )


@router.post("/finalize-resume", response_model=ApiResponse)
async def finalize_resume_route(payload: FinalizeRequest):
    sess = _get_session(payload.session_id)
    if not sess.jd_analysis:
        raise HTTPException(400, "请先完成 JD 分析")

    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
    if pending:
        raise HTTPException(400, f"仍有 {len(pending)} 条建议未处理，请先接受或拒绝")

    try:
        result = await finalize_resume(sess, force=payload.force)
    except FinalizeBlocked as e:
        # 结构化返回：前端据此渲染「压缩 / 改稿 / 仍然导出」三条出路
        raise HTTPException(
            status_code=409,
            detail={"code": "finalize_blocked", "message": str(e), "issues": e.issues},
        ) from e
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
            "emphasis_phrases": result.get("emphasis_phrases") or [],
            "finalize_status": sess.finalize_status,
            "forced": payload.force,
        },
    )


@router.get("/finalize-status/{session_id}", response_model=ApiResponse)
async def finalize_status(session_id: str):
    sess = _get_session(session_id)
    return ApiResponse(
        success=True,
        data={
            "finalize_status": sess.finalize_status,
            "finalized_markdown": sess.finalized_resume_md,
            "working_markdown": sess.current_resume_md,
        },
    )


@router.post("/unfinalize-resume", response_model=ApiResponse)
async def unfinalize_resume_route(payload: SessionRequest):
    """撤销定稿，回到改稿态（工作稿继续可编辑）。"""
    sess = _get_session(payload.session_id)
    sess.finalize_status = "draft"
    store.update(sess)
    return ApiResponse(
        success=True,
        data={
            "finalize_status": sess.finalize_status,
            "current_resume_md": sess.current_resume_md,
        },
    )
