"""匹配度 + 修改建议 router。"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.application_advisor import application_decision
from app.services.match_analyzer import analyze_match
from app.services.resume_from_knowledge import build_resume_from_knowledge
from app.services.resume_density import assess_density
from app.services.session_store import store
from app.services.suggestion_engine import generate_suggestions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


class SessionRef(BaseModel):
    session_id: str
    knowledge_base: str = ""
    client_id: str = "default"
    regenerate_suggestions: bool = True


@router.post("/build-resume-from-knowledge", response_model=ApiResponse)
async def build_resume_from_knowledge_route(payload: SessionRef):
    """根据知识库 + 当前 JD 生成工作稿简历，并可选重新生成修改建议。"""
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    if not sess.jd_analysis:
        raise HTTPException(400, "请先完成岗位分析")

    try:
        result = await build_resume_from_knowledge(
            sess,
            knowledge_base=payload.knowledge_base,
            client_id=payload.client_id,
            regenerate_suggestions=payload.regenerate_suggestions,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("build resume from knowledge failed")
        raise HTTPException(500, f"生成失败: {e}") from e

    return ApiResponse(success=True, data=result)


@router.post("/analyze-match", response_model=ApiResponse)
async def analyze_match_route(payload: SessionRef):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    if not sess.jd_analysis or not sess.current_resume_md:
        raise HTTPException(400, "请先完成简历解析与 JD 分析")

    match = await analyze_match(sess.current_resume_md, sess.jd_analysis)
    sess.match_result = match
    sess.status = "matched"
    store.update(sess)

    return ApiResponse(
        success=True,
        data={
            "match": match.model_dump(),
            "decision": application_decision(match, sess.jd_analysis),
        },
    )


@router.post("/generate-suggestions", response_model=ApiResponse)
async def generate_suggestions_route(payload: SessionRef):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    if not sess.jd_analysis or not sess.current_resume_md or not sess.match_result:
        raise HTTPException(400, "请先完成匹配度分析")

    kb = payload.knowledge_base.strip() or sess.knowledge_base_md
    if kb:
        sess.knowledge_base_md = kb

    suggestions, summary = await generate_suggestions(
        sess.current_resume_md,
        sess.jd_analysis,
        sess.match_result,
        knowledge_base=kb,
        session_id=sess.session_id,
        profile_photo_ref=sess.profile_photo_ref,
    )
    sess.suggestions = suggestions
    sess.status = "suggestions_ready"
    store.update(sess)

    return ApiResponse(
        success=True,
        data={
            "suggestions": [s.model_dump() for s in suggestions],
            "summary": summary,
            "density": assess_density(sess.current_resume_md),
        },
    )
