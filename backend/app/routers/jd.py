"""JD 分析 router。"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.jd_analyzer import analyze_jd
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jd"])


class JDInput(BaseModel):
    session_id: str
    jd_text: str


@router.post("/analyze-jd", response_model=ApiResponse)
async def analyze_jd_route(payload: JDInput):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")

    try:
        jd = await analyze_jd(payload.jd_text)
    except ValueError as e:
        raise HTTPException(400, str(e))

    sess.jd_text = payload.jd_text
    sess.jd_analysis = jd
    sess.status = "jd_analyzed"
    store.update(sess)

    return ApiResponse(success=True, data={"analysis": jd.model_dump()})
