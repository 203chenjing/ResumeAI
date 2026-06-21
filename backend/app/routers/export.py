"""PDF 导出 router。"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.pdf_exporter import export_pdf
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["export"])


class ExportRequest(BaseModel):
    session_id: str
    mode: str = "standard"  # standard | diff
    filename: str = ""


def _export_markdown(sess, mode: str) -> str:
    if sess.finalize_status != "finalized" or not sess.finalized_resume_md:
        raise HTTPException(400, "请先确认定稿，再导出 PDF")
    if mode == "diff" and sess.suggestions:
        return _build_diff_markdown(sess.original_resume_md, sess.finalized_resume_md, sess.suggestions)
    return sess.finalized_resume_md


@router.post("/export-layout-check", response_model=ApiResponse)
async def export_layout_check(payload: ExportRequest):
    """定稿后检查页底空白、字数密度与 Markdown 空行（导出前预览用）。"""
    from app.services.pdf_exporter import validate_resume_markdown

    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    if sess.finalize_status != "finalized" or not sess.finalized_resume_md:
        raise HTTPException(400, "请先确认定稿")

    validation = validate_resume_markdown(sess.finalized_resume_md, session_id=payload.session_id)
    density = validation.get("density") or {}
    return ApiResponse(
        success=True,
        data={
            "page_count": validation.get("page_count", 0),
            "page_passed": validation.get("page_passed", False),
            "bottom_gap_mm": validation.get("bottom_gap_mm"),
            "char_count": density.get("char_count"),
            "density_status": density.get("status"),
            "density_message": density.get("message"),
            "layout_issues": validation.get("layout_issues", []),
            "skill_issues": validation.get("skill_issues", []),
            "ok": bool(validation.get("page_passed") and validation.get("skill_passed")),
        },
    )


@router.post("/export-pdf")
async def export_pdf_route(payload: ExportRequest):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")

    md_text = _export_markdown(sess, payload.mode)

    company = sess.jd_analysis.company if sess.jd_analysis and sess.jd_analysis.company else "目标公司"
    name = sess.parsed_resume.header.name if sess.parsed_resume else "候选人"
    role = sess.jd_analysis.role if sess.jd_analysis and sess.jd_analysis.role else "目标岗位"
    filename = payload.filename or f"{company}+{name}+{role}.pdf"

    try:
        pdf_path = export_pdf(md_text, filename, mode=payload.mode, session_id=payload.session_id)
    except Exception as e:
        logger.exception("PDF export failed")
        raise HTTPException(500, f"PDF 生成失败: {e}")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.post("/preview-pdf", response_model=ApiResponse)
async def preview_pdf(payload: ExportRequest):
    """生成 PDF 但仅返回路径（前端可通过 /api/exports/{filename} 访问）。"""
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")

    md_text = _export_markdown(sess, payload.mode)

    company = sess.jd_analysis.company if sess.jd_analysis and sess.jd_analysis.company else "目标公司"
    name = sess.parsed_resume.header.name if sess.parsed_resume else "候选人"
    role = sess.jd_analysis.role if sess.jd_analysis and sess.jd_analysis.role else "目标岗位"
    filename = payload.filename or f"{company}+{name}+{role}.pdf"

    pdf_path = export_pdf(md_text, filename, mode=payload.mode, session_id=payload.session_id)
    return ApiResponse(success=True, data={"filename": pdf_path.name, "url": f"/api/download/{pdf_path.name}"})


@router.get("/download/{filename}")
async def download(filename: str):
    from app.services.pdf_exporter import EXPORT_DIR
    path = EXPORT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path, media_type="application/pdf", filename=filename)


def _build_diff_markdown(original: str, current: str, suggestions: list) -> str:
    """生成带 diff 标记的 markdown：接受的建议用 <ins>/<del> 包裹。"""
    md = original
    for s in suggestions:
        if s.status == "accepted" and s.original_text and s.suggested_text:
            md = md.replace(
                s.original_text,
                f"<del>{s.original_text}</del> <ins>{s.suggested_text}</ins>",
                1,
            )
    return md
