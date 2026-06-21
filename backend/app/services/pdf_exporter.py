"""PDF 导出服务：调用 tools/markdown_resume_to_pdf.py。"""
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = BACKEND_ROOT / "tools"
EXPORT_DIR = BACKEND_ROOT / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def check_markdown_skill(md_path: Path) -> tuple[bool, list[str]]:
    """运行 check_resume_skill.py --markdown-only。"""
    cmd = [
        sys.executable,
        str(TOOLS_DIR / "check_resume_skill.py"),
        str(md_path),
        "--markdown-only",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return True, []
    issues: list[str] = []
    for line in (result.stdout + result.stderr).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            issues.append(stripped[2:])
        elif stripped and stripped not in ("Skill check: failed.", "Skill check: passed."):
            if "Skill check" not in stripped:
                issues.append(stripped)
    return False, issues or ["Markdown 格式自检未通过"]


def validate_resume_markdown(markdown: str, session_id: str = "") -> dict:
    """校验 Markdown 格式 + 导出页数（临时目录；可 staging 照片）。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        staged = markdown
        if session_id:
            from app.services.profile_photo import stage_photo_for_export

            staged = stage_photo_for_export(markdown, session_id, tmp)
        md_path = tmp / "validate.md"
        pdf_path = tmp / "validate.pdf"
        md_path.write_text(staged, encoding="utf-8")

        skill_passed, skill_issues = check_markdown_skill(md_path)
        page_count = 0
        page_passed = False
        layout_issues: list[str] = []

        cmd = [
            sys.executable,
            str(TOOLS_DIR / "markdown_resume_to_pdf.py"),
            str(md_path),
            "-o",
            str(pdf_path),
            "--mode",
            "standard",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if pdf_path.exists():
            from PyPDF2 import PdfReader

            page_count = len(PdfReader(str(pdf_path)).pages)
            page_passed = page_count == 1
            if page_count > 1:
                layout_issues.append(f"PDF 为 {page_count} 页，必须为 1 页")
            elif page_count == 0:
                layout_issues.append("PDF 页数为 0")
            else:
                from tools.markdown_resume_to_pdf import validate_pdf_photo_layout

                layout_issues.extend(validate_pdf_photo_layout(pdf_path))
        elif result.returncode != 0:
            layout_issues.append(result.stderr.strip() or result.stdout.strip() or "PDF 生成失败")

        # 页数脚本通过但底部空白仍需人工密度判断：用字符数粗估
        if page_passed and len(staged.strip()) < 900:
            layout_issues.append("内容过短，单页底部可能空白过多")
            page_passed = False

        return {
            "skill_passed": skill_passed,
            "skill_issues": skill_issues,
            "page_count": page_count,
            "page_passed": page_passed and not layout_issues,
            "layout_issues": layout_issues,
        }


def export_pdf(
    markdown: str,
    filename: str,
    mode: str = "standard",
    session_id: str = "",
) -> Path:
    """导出 PDF。

    mode: standard | diff（diff 由前端在 markdown 中预先标记 <ins>/<del>）
    返回生成的 PDF 路径。
    """
    from app.services.profile_photo import stage_photo_for_export

    md_path = EXPORT_DIR / f"{filename.replace('.pdf', '')}.md"
    pdf_path = EXPORT_DIR / filename

    staged_md = markdown
    if session_id:
        staged_md = stage_photo_for_export(markdown, session_id, EXPORT_DIR)
    md_path.write_text(staged_md, encoding="utf-8")

    cmd = [
        sys.executable,
        str(TOOLS_DIR / "markdown_resume_to_pdf.py"),
        str(md_path),
        "-o",
        str(pdf_path),
        "--mode",
        mode,
    ]
    logger.info(f"Run PDF export: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        logger.error(f"PDF export failed: stdout={result.stdout}, stderr={result.stderr}")
        raise RuntimeError(f"PDF 生成失败: {result.stderr or result.stdout}")
    if not pdf_path.exists():
        raise RuntimeError("PDF 文件未生成")
    return pdf_path
