"""母版简历 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.master_resume import get_active_master, list_masters, save_master

router = APIRouter(prefix="/api", tags=["master-resume"])


class SaveMasterBody(BaseModel):
    client_id: str = "default"
    markdown: str = Field(..., min_length=10)
    title: str = "母版简历"
    knowledge_hash: str = ""
    set_active: bool = True


@router.get("/master-resume/{client_id}", response_model=ApiResponse)
async def get_masters(client_id: str):
    active = get_active_master(client_id)
    return ApiResponse(
        success=True,
        data={"masters": list_masters(client_id), "active": active},
    )


@router.post("/master-resume", response_model=ApiResponse)
async def post_master(body: SaveMasterBody):
    master = save_master(
        body.client_id,
        body.markdown,
        title=body.title,
        knowledge_hash=body.knowledge_hash,
        set_active=body.set_active,
    )
    return ApiResponse(success=True, data=master)
