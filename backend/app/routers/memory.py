"""用户记忆 API：L4 长期记忆 + L5 会话摘要 + L6 AutoDream。"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services import auto_dream, memdir, session_memory
from app.services.session_store import store
from app.services.user_memory import load_memory, save_memory

router = APIRouter(prefix="/api", tags=["memory"])


class MemoryPayload(BaseModel):
    client_id: str = Field(default="default", max_length=64)
    knowledge_base_md: str = ""
    notes: str = ""
    preferences: dict | None = None


class ConsolidatePayload(BaseModel):
    client_id: str = Field(default="default", max_length=64)
    force: bool = False


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


@router.get("/memory/index/{client_id}", response_model=ApiResponse)
async def get_memory_index(client_id: str = "default"):
    memdir.ensure_memdir(client_id)
    return ApiResponse(
        success=True,
        data={"index": memdir.read_index(client_id), "topics": memdir.list_topics(client_id)},
    )


@router.get("/memory/topics/{client_id}/{topic_name}", response_model=ApiResponse)
async def get_memory_topic(client_id: str, topic_name: str):
    content = memdir.read_topic(client_id, topic_name)
    return ApiResponse(success=True, data={"topic": topic_name, "content": content})


@router.get("/memory/session/{session_id}", response_model=ApiResponse)
async def get_session_memory(session_id: str):
    return ApiResponse(success=True, data={"summary": session_memory.read_summary(session_id)})


@router.post("/memory/session/{session_id}/summarize", response_model=ApiResponse)
async def summarize_session(session_id: str):
    sess = store.get(session_id)
    if not sess:
        return ApiResponse(success=False, error="会话不存在或已过期")
    summary = session_memory.build_rolling_summary(sess)
    session_memory.write_summary(session_id, summary)
    return ApiResponse(success=True, data={"summary": summary})


@router.get("/memory/dream-status/{client_id}", response_model=ApiResponse)
async def get_dream_status(client_id: str = "default"):
    return ApiResponse(success=True, data=auto_dream.dream_status(client_id))


@router.post("/memory/consolidate", response_model=ApiResponse)
async def consolidate_memory(payload: ConsolidatePayload):
    result = auto_dream.consolidate(payload.client_id, force=payload.force)
    return ApiResponse(success=result.get("success", False), data=result)
