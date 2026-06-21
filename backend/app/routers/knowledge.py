"""简历知识库 router（含个人照片自定义模块）。"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.profile_photo import (
    apply_photo_to_markdown,
    delete_session_photo,
    has_session_photo,
    photo_ref_for_session,
    save_session_photo,
    session_photo_path,
    strip_photo_from_markdown,
)
from app.services.session_store import store

router = APIRouter(prefix="/api", tags=["knowledge"])

KNOWLEDGE_TEMPLATE = """# 简历知识库

> 经用户确认的经历素材库，供改简历时抽取 STAR、指标与项目事实。比投递简历更完整。

## 个人自定义模块

### 个人照片
- 用途：导出 PDF 时显示在右上角（540×790 比例，自动裁剪）
- 操作：在页面上传证件照/半身照；保存后自动写入简历 Markdown
- 要求：人脸清晰、背景简洁；导出前请确认预览中照片完整可见

## 使用规则
- 只写已确认事实；不确定的指标标 `[待确认]`
- 同一雇主下多条工作线保持并列，不写父子层级

## 实习 / 项目素材

### 公司名 · 岗位 · 时间
- **背景**：
- **任务**：
- **行动**：
- **结果**（指标/影响）：
- **关键词**：

## 指标清单
| 指标 | 数值 | 来源 |
|------|------|------|

## 待确认
- 
"""


class KnowledgeBasePayload(BaseModel):
    session_id: str
    content: str = Field(default="", max_length=100_000)


def _sync_photo_into_resume(sess) -> None:
    if sess.profile_photo_ref and has_session_photo(sess.session_id):
        sess.current_resume_md = apply_photo_to_markdown(
            sess.current_resume_md, sess.profile_photo_ref
        )
    else:
        sess.current_resume_md = strip_photo_from_markdown(sess.current_resume_md)


@router.get("/knowledge-base/template", response_model=ApiResponse)
async def knowledge_template():
    return ApiResponse(success=True, data={"template": KNOWLEDGE_TEMPLATE})


@router.get("/knowledge-base/{session_id}", response_model=ApiResponse)
async def get_knowledge(session_id: str):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    return ApiResponse(
        success=True,
        data={
            "content": sess.knowledge_base_md,
            "has_content": bool(sess.knowledge_base_md.strip()),
            "has_photo": has_session_photo(session_id),
            "photo_url": f"/api/knowledge-base/photo/{session_id}" if has_session_photo(session_id) else "",
        },
    )


@router.put("/knowledge-base", response_model=ApiResponse)
async def save_knowledge(payload: KnowledgeBasePayload):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    sess.knowledge_base_md = payload.content.strip()
    _sync_photo_into_resume(sess)
    store.update(sess)
    return ApiResponse(
        success=True,
        data={
            "content": sess.knowledge_base_md,
            "current_markdown": sess.current_resume_md,
            "has_photo": has_session_photo(sess.session_id),
        },
    )


@router.post("/knowledge-base/photo", response_model=ApiResponse)
async def upload_photo(session_id: str = Form(...), file: UploadFile = File(...)):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")

    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "照片超过 5MB")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "请上传图片文件（JPG/PNG）")

    try:
        ref = save_session_photo(session_id, raw)
    except Exception as e:
        raise HTTPException(400, f"照片处理失败: {e}") from e

    sess.profile_photo_ref = ref
    _sync_photo_into_resume(sess)
    if sess.finalize_status == "finalized":
        sess.finalize_status = "stale"
    store.update(sess)

    return ApiResponse(
        success=True,
        data={
            "photo_ref": ref,
            "photo_url": f"/api/knowledge-base/photo/{session_id}",
            "current_markdown": sess.current_resume_md,
            "finalize_status": sess.finalize_status,
        },
    )


@router.get("/knowledge-base/photo/{session_id}")
async def get_photo(session_id: str):
    path = session_photo_path(session_id)
    if not path.exists():
        raise HTTPException(404, "未上传照片")
    return FileResponse(path, media_type="image/png", filename="profile-photo.png")


@router.delete("/knowledge-base/photo/{session_id}", response_model=ApiResponse)
async def remove_photo(session_id: str):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    delete_session_photo(session_id)
    sess.profile_photo_ref = ""
    sess.current_resume_md = strip_photo_from_markdown(sess.current_resume_md)
    if sess.finalized_resume_md:
        sess.finalized_resume_md = strip_photo_from_markdown(sess.finalized_resume_md)
    if sess.finalize_status == "finalized":
        sess.finalize_status = "stale"
    store.update(sess)
    return ApiResponse(success=True, data={"current_markdown": sess.current_resume_md})
