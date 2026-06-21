"""投递追踪 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.application_store import (
    create_application,
    delete_application,
    funnel_stats,
    list_applications,
    update_status,
)

router = APIRouter(prefix="/api", tags=["applications"])


class CreateApplicationBody(BaseModel):
    client_id: str = "default"
    company: str = ""
    role: str = ""
    channel: str = "官网"
    jd_text: str = ""
    jd_url: str = ""
    match_score: int = 0
    decision_level: str = ""
    status: str = "Evaluated"
    session_id: str = ""
    resume_pdf_path: str = ""
    deadline: str = ""
    notes: str = ""


class UpdateStatusBody(BaseModel):
    client_id: str = "default"
    app_id: str
    status: str
    notes: str = ""


@router.get("/applications/{client_id}", response_model=ApiResponse)
async def get_applications(client_id: str):
    return ApiResponse(
        success=True,
        data={"applications": list_applications(client_id), "stats": funnel_stats(client_id)},
    )


@router.post("/applications", response_model=ApiResponse)
async def post_application(body: CreateApplicationBody):
    app = create_application(body.client_id, body.model_dump())
    return ApiResponse(success=True, data=app)


@router.patch("/applications/status", response_model=ApiResponse)
async def patch_status(body: UpdateStatusBody):
    try:
        app = update_status(body.client_id, body.app_id, body.status, body.notes)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return ApiResponse(success=True, data=app)


@router.delete("/applications/{client_id}/{app_id}", response_model=ApiResponse)
async def delete_application_route(client_id: str, app_id: str):
    try:
        app = delete_application(client_id, app_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return ApiResponse(success=True, data=app)
