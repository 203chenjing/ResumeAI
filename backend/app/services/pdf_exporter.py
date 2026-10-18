"""PDF 导出服务：调用 tools/markdown_resume_to_pdf.py。"""
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = BACKEND_ROOT / "tools"
EXPORT_DIR = BACKEND_ROOT / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_NAME_LEN = 120


def safe_export_filename(filename: str, *, default: str = "resume.pdf") -> str:
    """把外部传入的文件名收敛成 `exports/` 下的纯文件名。

    防目录穿越与绝对路径写入：`../../.env`、`C:\\Windows\\x.pdf` 都会退化成
    单段文件名；Windows 保留字符统一替换为下划线。
    """
    name = Path(str(filename or "").strip().replace("\\", "/")).name
    name = _UNSAFE_CHARS.sub("_", name).strip().strip(".")
    if not name:
        return default
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    if len(name) > _MAX_NAME_LEN:
        # 截断时保留扩展名，避免产物变成无后缀文件
        name = f"{name[:-4][: _MAX_NAME_LEN - 4]}.pdf"
    return name


def _tool_failure_message(result: subprocess.CompletedProcess) -> str:
    """把渲染工具的堆栈收敛成一句可操作提示（不把 traceback 抛给前端）。"""
    output = f"{result.stderr or ''}\n{result.stdout or ''}"
    lowered = output.lower()
    if "executable doesn't exist" in lowered or "playwright install" in lowered:
        return "PDF 渲染组件不可用：请先执行 `python -m playwright install chromium` 后重试"
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    last = lines[-1] if lines else "PDF 生成失败"
    return f"PDF 生成失败：{last[:160]}"



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
        bottom_gap_mm = None

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
                from tools.markdown_resume_to_pdf import (
                    check_markdown_spacing,
                    measure_pdf_bottom_gap,
                    validate_pdf_photo_layout,
                )

                layout_issues.extend(check_markdown_spacing(staged))
                layout_issues.extend(validate_pdf_photo_layout(pdf_path))
                gap_info = measure_pdf_bottom_gap(pdf_path)
                layout_issues.extend(gap_info.get("issues", []))
                bottom_gap_mm = gap_info.get("bottom_gap_mm")
        elif result.returncode != 0:
            layout_issues.append(_tool_failure_message(result))
            bottom_gap_mm = None
        else:
            bottom_gap_mm = None

        from app.services.resume_density import SPARSE_THRESHOLD, assess_density

        density = assess_density(staged)
        # 页数通过但字数偏少：单页底部易留白（与 SKILL 1500 字下限对齐）
        if page_passed and density["char_count"] < SPARSE_THRESHOLD:
            layout_issues.append(
                f"内容约 {density['char_count']} 字，偏少，一页底部可能留白较多"
            )
            page_passed = False
        elif page_passed and len(staged.strip()) < 900:
            layout_issues.append("内容偏少，一页底部可能留白较多")
            page_passed = False

        return {
            "skill_passed": skill_passed,
            "skill_issues": skill_issues,
            "page_count": page_count,
            "page_passed": page_passed and not layout_issues,
            "layout_issues": layout_issues,
            "bottom_gap_mm": bottom_gap_mm,
            "density": density,
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

    filename = safe_export_filename(filename)
    md_path = EXPORT_DIR / f"{filename[:-4]}.md"
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

    layout_warnings = check_export_layout_warnings(pdf_path, staged_md)
    if layout_warnings:
        logger.warning("PDF export layout warnings: %s", "; ".join(layout_warnings))
    return pdf_path


def check_export_layout_warnings(pdf_path: Path, markdown: str) -> list[str]:
    """导出后软性检查：记录页底空白与空行问题（不阻断下载）。"""
    from tools.markdown_resume_to_pdf import (
        check_markdown_spacing,
        measure_pdf_bottom_gap,
        validate_pdf_photo_layout,
    )

    warnings: list[str] = []
    warnings.extend(check_markdown_spacing(markdown))
    warnings.extend(validate_pdf_photo_layout(pdf_path))
    gap_info = measure_pdf_bottom_gap(pdf_path)
    warnings.extend(gap_info.get("issues", []))
    return warnings
