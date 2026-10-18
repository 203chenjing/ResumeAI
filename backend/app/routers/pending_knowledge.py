"""知识库待沉淀 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.pending_knowledge import (
    confirm_pending,
    list_pending,
    merge_confirmed_into_kb,
)
from app.services.user_memory import load_memory, save_memory

router = APIRouter(prefix="/api", tags=["pending-knowledge"])


class ConfirmPendingBody(BaseModel):
    client_id: str = "default"
    entry_id: str
    action: str = Field(pattern="^(confirm|ignore)$")
    target_title: str = ""


@router.get("/pending-knowledge/{client_id}", response_model=ApiResponse)
async def get_pending(client_id: str, status: str = "pending"):
    items = list_pending(client_id, status if status else None)
    return ApiResponse(success=True, data={"items": items})


@router.post("/pending-knowledge/confirm", response_model=ApiResponse)
async def post_confirm(body: ConfirmPendingBody):
    try:
        item = confirm_pending(body.client_id, body.entry_id, body.action, body.target_title)
    except ValueError as e:
        # 参数问题（如未选归属经历）是 400，不是 404；404 只用于条目不存在
        status = 404 if "不存在" in str(e) else 400
        raise HTTPException(status, str(e)) from e
    return ApiResponse(success=True, data=item)


@router.post("/pending-knowledge/merge-to-kb", response_model=ApiResponse)
async def merge_to_kb(client_id: str = "default"):
    mem = load_memory(client_id)
    kb = merge_confirmed_into_kb(mem.get("knowledge_base_md", ""), client_id)
    save_memory(client_id, {"knowledge_base_md": kb})
    return ApiResponse(success=True, data={"knowledge_base_md": kb})
