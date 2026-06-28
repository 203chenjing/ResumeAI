"""Hub 智能简报 API：今日卡、准备度、行为飞轮、漏斗、批量 tailoring、ATS 回读。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.ats_readback import ats_readback_check
from app.services.batch_tailor import batch_tailor_preview, suggest_batch_job_ids
from app.services.behavior_signals import get_behavior_profile, record_event, update_steer
from app.services.funnel_metrics import funnel_summary, record_funnel_event
from app.services.job_readiness import compute_readiness, explain_job_rank, rank_jobs_with_readiness
from app.services.job_feed import list_jobs
from app.services.master_resume import get_active_master
from app.services.pdf_exporter import EXPORT_DIR
from app.services.session_store import store
from app.services.today_briefing import build_aha_after_upload, build_today_briefing
from app.services.user_memory import load_memory

router = APIRouter(prefix="/api/hub", tags=["hub"])


class BehaviorEventBody(BaseModel):
    client_id: str = "default"
    event_type: str
    job_id: str = ""
    company: str = ""
    role: str = ""
    meta: dict = Field(default_factory=dict)


class SteerBody(BaseModel):
    client_id: str = "default"
    boost_companies: list[str] = Field(default_factory=list)
    boost_cities: list[str] = Field(default_factory=list)
    block_companies: list[str] = Field(default_factory=list)


class FunnelBody(BaseModel):
    client_id: str = "default"
    step: str
    meta: dict = Field(default_factory=dict)


class ReadinessBody(BaseModel):
    client_id: str = "default"
    job_id: str
    resume_md: str = ""


class BatchTailorBody(BaseModel):
    client_id: str = "default"
    job_ids: list[str] = Field(default_factory=list)
    resume_md: str = ""


class AtsReadbackBody(BaseModel):
    session_id: str
    client_id: str = "default"
    filename: str = ""


def _resume_md(client_id: str, override: str = "") -> str:
    if override.strip():
        return override
    master = get_active_master(client_id)
    if master and master.get("markdown"):
        return master["markdown"]
    return load_memory(client_id).get("knowledge_base_md", "") or ""


@router.get("/today/{client_id}", response_model=ApiResponse)
async def get_today_briefing(client_id: str):
    return ApiResponse(success=True, data=build_today_briefing(client_id))


@router.get("/aha/{client_id}", response_model=ApiResponse)
async def get_aha(client_id: str, resume_md: str = ""):
    md = resume_md or _resume_md(client_id)
    return ApiResponse(success=True, data=build_aha_after_upload(client_id, md))


@router.get("/readiness/{client_id}/{job_id}", response_model=ApiResponse)
async def get_readiness(client_id: str, job_id: str, resume_md: str = ""):
    job = next((j for j in list_jobs(client_id, include_weak=False) if j.get("id") == job_id), None)
    if not job:
        raise HTTPException(404, "岗位不存在")
    md = _resume_md(client_id, resume_md)
    rd = compute_readiness(job, resume_md=md, client_id=client_id)
    return ApiResponse(success=True, data={**rd, "explain": explain_job_rank(job, rd)})


@router.post("/readiness/rank", response_model=ApiResponse)
async def post_readiness_rank(body: ReadinessBody):
    jobs = list_jobs(body.client_id, include_weak=False)
    md = _resume_md(body.client_id, body.resume_md)
    if not md.strip():
        raise HTTPException(400, "需要简历才能排序")
    ranked = rank_jobs_with_readiness(body.client_id, jobs, md, top_k=12)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "job": r["job"],
                    "hybrid_score": r["hybrid_score"],
                    "readiness": r["readiness"],
                    "behavior_reasons": r.get("behavior_reasons", []),
                }
                for r in ranked
            ]
        },
    )


@router.post("/behavior/event", response_model=ApiResponse)
async def post_behavior_event(body: BehaviorEventBody):
    record_event(
        body.client_id,
        body.event_type,
        job_id=body.job_id,
        company=body.company,
        role=body.role,
        meta=body.meta,
    )
    if body.event_type == "tailor_start":
        record_funnel_event(body.client_id, "job_tailor_start", meta={"job_id": body.job_id})
    elif body.event_type == "apply_mark":
        record_funnel_event(body.client_id, "apply_marked", meta={"job_id": body.job_id})
    return ApiResponse(success=True, data={"ok": True})


@router.get("/behavior/{client_id}", response_model=ApiResponse)
async def get_behavior(client_id: str):
    return ApiResponse(success=True, data=get_behavior_profile(client_id))


@router.put("/behavior/steer", response_model=ApiResponse)
async def put_behavior_steer(body: SteerBody):
    steer = update_steer(
        body.client_id,
        boost_companies=body.boost_companies or None,
        boost_cities=body.boost_cities or None,
        block_companies=body.block_companies or None,
    )
    return ApiResponse(success=True, data=steer)


@router.post("/funnel/event", response_model=ApiResponse)
async def post_funnel_event(body: FunnelBody):
    record_funnel_event(body.client_id, body.step, meta=body.meta)
    return ApiResponse(success=True, data={"ok": True})


@router.get("/funnel/{client_id}", response_model=ApiResponse)
async def get_funnel(client_id: str, days: int = 7):
    return ApiResponse(success=True, data=funnel_summary(client_id, days=days))


@router.post("/batch-tailor", response_model=ApiResponse)
async def post_batch_tailor(body: BatchTailorBody):
    ids = body.job_ids
    if not ids:
        ids = suggest_batch_job_ids(body.client_id, body.resume_md)
    try:
        rows = batch_tailor_preview(body.client_id, ids, resume_md=body.resume_md)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ApiResponse(success=True, data={"items": rows, "job_ids": ids})


@router.post("/ats-readback", response_model=ApiResponse)
async def post_ats_readback(body: AtsReadbackBody):
    sess = store.get(body.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    md = sess.finalized_resume_md or sess.current_resume_md or ""
    if not md.strip():
        raise HTTPException(400, "无定稿简历可检测")

    filename = body.filename
    if not filename:
        company = sess.jd_analysis.company if sess.jd_analysis else "目标公司"
        name = sess.parsed_resume.header.name if sess.parsed_resume else "候选人"
        role = sess.jd_analysis.role if sess.jd_analysis else "目标岗位"
        filename = f"{company}+{name}+{role}.pdf"

    pdf_path = EXPORT_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(404, "PDF 不存在，请先导出")

    result = ats_readback_check(pdf_path, md)
    record_funnel_event(body.client_id, "export_pdf", meta={"ats_score": result.get("ats_score")})
    return ApiResponse(success=True, data=result)
