"""ATS 回读：导出 PDF 后检测机器是否可读（对标 Jobscan 核心卖点）。"""
from __future__ import annotations

import re
from pathlib import Path

from app.services.match_engine import tokenize


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz  # pymupdf

        doc = fitz.open(pdf_path)
        parts = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(parts)
    except Exception:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(pdf_path))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            return ""


def ats_readback_check(pdf_path: Path, source_markdown: str) -> dict:
    """对比 PDF 提取文本与源 Markdown，评估 ATS 可读性。"""
    extracted = extract_pdf_text(pdf_path)
    src_tokens = set(tokenize(source_markdown))
    pdf_tokens = set(tokenize(extracted))

    if not extracted.strip():
        return {
            "ats_score": 0,
            "readable": False,
            "char_extracted": 0,
            "keyword_retention": 0.0,
            "issues": ["PDF 无法提取文本，ATS 可能无法解析（疑似纯图片/乱码）"],
            "missing_keywords": [],
        }

    retention = len(src_tokens & pdf_tokens) / max(len(src_tokens), 1)
    issues: list[str] = []
    if retention < 0.35:
        issues.append("关键词保留率过低，ATS 可能读不全你的经历要点")
    if len(extracted) < len(re.sub(r"\s+", "", source_markdown)) * 0.25:
        issues.append("提取字符数明显少于简历正文，排版可能干扰解析")
    if re.search(r"[\u4e00-\u9fff]{1,2}\s[\u4e00-\u9fff]{1,2}", extracted):
        issues.append("检测到异常断字，可能是多栏/表格导致 ATS 乱序")

    missing = [t for t in list(src_tokens)[:30] if t not in pdf_tokens and len(t) > 2][:12]
    score = int(min(98, max(10, round(retention * 85 + (15 if len(extracted) > 200 else 0)))))

    return {
        "ats_score": score,
        "readable": retention >= 0.35 and len(extracted) > 100,
        "char_extracted": len(extracted),
        "keyword_retention": round(retention, 3),
        "issues": issues,
        "missing_keywords": missing,
    }
