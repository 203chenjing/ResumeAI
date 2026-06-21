"""简历上传 + 解析 router。"""
import logging
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import ApiResponse
from app.services.parser import parse_resume_text
from app.services.session_store import store
from app.utils.file_handler import extract_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["resume"])


@router.post("/parse-resume", response_model=ApiResponse)
async def parse_resume(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(413, f"文件超过 {settings.max_file_size_mb}MB 限制")

    try:
        text, fmt = extract_text(file.filename or "resume", raw)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not text.strip():
        raise HTTPException(400, "未检测到可识别文本，请确认文件内容")

    parsed, md = await parse_resume_text(text)

    sess = store.create()
    sess.original_resume_md = md
    sess.current_resume_md = md
    sess.parsed_resume = parsed
    sess.status = "parsed"
    store.update(sess)

    return ApiResponse(
        success=True,
        data={
            "session_id": sess.session_id,
            "format": fmt,
            "parsed": parsed.model_dump(),
            "markdown": md,
        },
    )
