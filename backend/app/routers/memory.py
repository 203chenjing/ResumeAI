"""用户长期记忆 API。"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.user_memory import load_memory, save_memory

router = APIRouter(prefix="/api", tags=["memory"])


class MemoryPayload(BaseModel):
    client_id: str = Field(default="default", max_length=64)
    knowledge_base_md: str = ""
    notes: str = ""
    preferences: dict | None = None


@router.get("/user-memory/{client_id}", response_model=ApiResponse)
async def get_memory(client_id: str = "default"):
    return ApiResponse(success=True, data=load_memory(client_id))


@router.put("/user-memory", response_model=ApiResponse)
async def put_memory(payload: MemoryPayload):
    data = save_memory(
        payload.client_id,
        {
            "knowledge_base_md": payload.knowledge_base_md,
            "notes": payload.notes,
            "preferences": payload.preferences or {},
        },
    )
    return ApiResponse(success=True, data=data)
