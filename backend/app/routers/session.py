"""会话状态查询。"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import ApiResponse
from app.services.session_store import store

router = APIRouter(prefix="/api", tags=["session"])


@router.get("/session/{session_id}", response_model=ApiResponse)
async def get_session(session_id: str):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    return ApiResponse(success=True, data=sess.model_dump(mode="json"))
