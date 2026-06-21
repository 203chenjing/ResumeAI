"""Markdown 简历 → A4 单页 PDF 导出器（Playwright + Chromium 渲染）。

排版规范：SKILL.md「Markdown to PDF Layout Standard」+ resume-pdf-export SKILL。
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import markdown
from PyPDF2 import PdfReader

BACKEND_ROOT = Path(__file__).resolve().parents[1]

PRESETS = {
    "standard": {
        "margin_bottom": "0.8cm",
        "item_spacing": "3pt",
        "section_margin": "4pt",
        "h2_after": "3pt",
        "body_padding_top": "0",
    },
    "tight": {
        "margin_bottom": "0.8cm",
        "item_spacing": "2pt",
        "section_margin": "3pt",
        "h2_after": "2pt",
        "body_padding_top": "8mm",
    },
    "fill": {
        "margin_bottom": "0.6cm",
        "item_spacing": "3pt",
        "section_margin": "4pt",
        "h2_after": "3pt",
        "body_padding_top": "14mm",
    },
}

PHOTO_RESERVE_PT = 64
FIXED_LINE_HEIGHT = "1.3"

HEADER_LONG_NAME_THRESHOLD = 13

ROLE_HINT_RE = re.compile(
    r"(实习生|工程师|经理|专员|顾问|管培|分析师|设计师|开发|产品|运营|方向|管培生)"
)
CITY_NAMES = frozenset(
    {"上海", "北京", "深圳", "广州", "杭州", "南京", "成都", "武汉", "西安", "苏州"}
)

HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 1.0cm 2.0cm {margin_bottom} 2.0cm;
}}
* {{
    box-sizing: border-box;
}}
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "SimHei", sans-serif;
    font-size: 9.5pt;
    line-height: {line_height};
    color: #111;
    margin: 0;
    padding: 0;
    padding-top: {body_padding_top};
    text-align: justify;
    widows: 2;
    orphans: 2;
    position: relative;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}}
h1 {{
    font-size: 17pt;
    font-weight: 700;
    text-align: center;
    margin: 0 0 3pt 0;
    line-height: {line_height};
}}
.contact-line,
.target-role {{
    text-align: center;
    text-align-last: center;
    font-size: 10pt;
    line-height: {line_height};
    margin: 0;
}}
.target-role {{
    font-weight: 700;
}}
.photo {{
    position: absolute;
    top: 0;
    right: 0;
    margin: 0;
    width: 58pt;
    height: 85pt;
    min-width: 58pt;
    max-width: 58pt;
    min-height: 85pt;
    max-height: 85pt;
    text-align: right;
    overflow: visible;
}}
.photo img {{
    display: block;
    width: 58pt;
    height: 85pt;
    min-width: 58pt;
    max-width: 58pt;
    min-height: 85pt;
    max-height: 85pt;
    object-fit: contain;
    object-position: center center;
    background: #fff;
    border: none;
}}
body.has-photo .resume-header-row {{
    display: grid;
    grid-template-columns: 46% 29% 25%;
    column-gap: 0;
    align-items: baseline;
    width: calc(100% - {photo_reserve}pt);
    max-width: calc(100% - {photo_reserve}pt);
}}
body.has-photo .resume-header-row > span {{
    display: block;
}}
body.has-photo .resume-header-row .col-left {{
    white-space: nowrap;
    word-break: keep-all;
}}
body.has-photo .col-mid,
body.has-photo .col-right {{
    text-align: center;
    white-space: nowrap;
}}
h2 {{
    font-size: 12.5pt;
    font-weight: 700;
    border: none;
    margin: {section_margin} 0 {h2_after} 0;
    padding: 0;
    line-height: {line_height};
}}
p, li {{
    margin: 0 0 {item_spacing} 0;
    line-height: {line_height};
}}
hr {{
    border: none;
    border-top: 1px solid #222;
    margin: 3pt 0 1pt 0;
    page-break-after: avoid;
}}
hr + h2 {{
    margin-top: 2pt;
}}
ol {{
    margin: 0;
    padding-left: 0;
    list-style-position: inside;
}}
ol li {{
    margin: 0 0 {item_spacing} 0;
    text-align: justify;
}}
.resume-header-row {{
    display: table;
    width: 100%;
    table-layout: fixed;
    font-size: 10.5pt;
    font-weight: 700;
    margin: 0 0 2pt 0;
    line-height: {line_height};
}}
.resume-header-row > span {{
    display: table-cell;
    vertical-align: bottom;
}}
.resume-header-row .col-left {{
    text-align: left;
    width: 46%;
    white-space: nowrap;
    word-break: keep-all;
}}
.resume-header-row .col-left.long-left {{
    font-size: 8.5pt;
    line-height: 1.2;
}}
.resume-header-row .col-mid {{
    text-align: center;
    width: 29%;
    white-space: nowrap;
}}
.resume-header-row .col-right {{
    text-align: center;
    width: 25%;
    white-space: nowrap;
}}
strong {{
    font-weight: 700;
}}
ins {{
    color: #0a7c2f;
    text-decoration: underline;
    background: #e6f7ec;
}}
del {{
    color: #b91c1c;
    text-decoration: line-through;
    background: #fee;
}}
</style>
</head>
<body{body_class}>
{body}
</body>
</html>"""


def resolve_image_paths(md_text: str, base_dir: Path) -> str:
    """将相对路径图片转为 data URI，供 Playwright set_content 内联渲染。"""
    import base64

    def repl(match: re.Match[str]) -> str:
        alt, url = match.group(1), match.group(2).strip()
        if url.startswith("data:"):
            return match.group(0)
        if url.startswith(("http://", "https://")):
            return match.group(0)
        path = None
        if url.startswith("file://"):
            path = Path(url[7:]).resolve()
        else:
            for candidate in (
                (base_dir / url).resolve(),
                (BACKEND_ROOT / url).resolve() if url.startswith("uploads/") else None,
            ):
                if candidate and candidate.exists():
                    path = candidate
                    break
        if not path or not path.exists():
            return match.group(0)
        suffix = path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"![{alt}](data:{mime};base64,{encoded})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md_text)


def _looks_like_role(text: str) -> bool:
    t = text.strip()
    return bool(ROLE_HINT_RE.search(t)) or "（" in t or "(" in t


def _looks_like_city(text: str) -> bool:
    t = text.strip()
    return t in CITY_NAMES or t.endswith("市")


def _format_contact_html(line: str) -> str:
    raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", line).strip()
    if raw.startswith("求职意向"):
        role = raw.split("：", 1)[-1].strip()
        return f'<p class="target-role"><strong>{role}</strong></p>'

    if raw.startswith("手机"):
        parts = re.split(r"\s*[|｜]\s*", raw)
        cleaned: list[str] = []
        for part in parts:
            p = part.strip()
            if p.startswith("手机："):
                cleaned.append(p.replace("手机：", "").strip())
            elif p.startswith("邮箱："):
                cleaned.append(p.replace("邮箱：", "").strip())
            else:
                cleaned.append(p)
        return f'<p class="contact-line">{" · ".join(cleaned)}</p>'

    parts = [p.strip() for p in re.split(r"\s*[·|｜]\s*", raw) if p.strip()]
    role = None
    if parts and _looks_like_role(parts[-1]) and not _looks_like_city(parts[-1]):
        role = parts.pop()
    html = f'<p class="contact-line">{" · ".join(parts)}</p>'
    if role:
        html += f'\n<p class="target-role"><strong>{role}</strong></p>'
    return html


def transform_contact_header(md: str) -> str:
    """姓名下方：联系行 + 求职意向分行（目标版式）。"""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# ") and not line.startswith("## "):
            out.append(line)
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                break
            nxt = lines[i].strip()
            if nxt.startswith("## ") or nxt.startswith("![个人照片]"):
                continue
            if "·" in nxt or "|" in nxt or "｜" in nxt or nxt.startswith("手机") or nxt.startswith("求职意向"):
                out.append("")
                out.append(_format_contact_html(nxt))
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                if i < len(lines) and lines[i].strip().startswith("求职意向"):
                    out.append(_format_contact_html(lines[i].strip()))
                    i += 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _normalize_header_left(left: str) -> str:
    """公司/学校名：去掉多余空格，避免在括号前断行。"""
    text = re.sub(r"\s+", "", left.strip())
    return text


def _merge_header_continuations(md: str) -> str:
    """合并被拆到下一行的公司后缀，如「(上海) 有限公司」。"""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    header_re = re.compile(
        r"^\*\*([^*]+)\*\*\s{2,}(.+?)\s{2,}(\d{4}\.\d{2}(?:-\d{4}\.\d{2}|-\S+)|至今)\s*$"
    )
    suffix_re = re.compile(r"^[\(（][^)）]+[\)）]?\s*有限公司$|^有限公司$")
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = header_re.match(stripped) if stripped.startswith("**") else None
        if m and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt and not nxt.startswith(("**", "#", "-", "*")) and not re.match(r"^\d+\.", nxt):
                if suffix_re.match(nxt) or ("公司" in nxt and len(nxt) <= 24):
                    left = _normalize_header_left(m.group(1) + nxt)
                    line = f"**{left}**  {m.group(2).strip()}  {m.group(3).strip()}"
                    i += 1
        out.append(line)
        i += 1
    return "\n".join(out)


def _header_row_html(left: str, mid: str, right: str) -> str:
    left_clean = _normalize_header_left(left)
    long_cls = " long-left" if len(left_clean) > HEADER_LONG_NAME_THRESHOLD else ""
    return (
        '<div class="resume-header-row">'
        f'<span class="col-left{long_cls}"><strong>{left_clean}</strong></span>'
        f'<span class="col-mid">{mid}</span>'
        f'<span class="col-right">{right}</span>'
        "</div>"
    )


def sanitize_export_placeholders(md: str) -> str:
    """导出前将待补充占位替换为可读文案，避免 PDF 出现方括号。"""
    return re.sub(r"\[待补充：[^\]]+\]", "若干", md)


def _parse_header_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("**"):
        return None
    m = re.match(
        r"^\*\*([^*]+)\*\*\s{2,}(.+?)\s{2,}(\d{4}\.\d{2}(?:-\d{4}\.\d{2}|-\S+)|至今)\s*$",
        stripped,
    )
    if m:
        return _header_row_html(m.group(1), m.group(2).strip(), m.group(3).strip())
    m = re.match(
        r"^\*\*([^*]+)\*\*\s{2,}(.+?)[，,]\s*(\d{4}\.\d{2}(?:-\d{4}\.\d{2}|-\S+))\s*$",
        stripped,
    )
    if m:
        return _header_row_html(m.group(1), m.group(2).strip(), m.group(3).strip())
    return None


def transform_header_rows(md: str) -> str:
    """教育/实习学校公司行 → 固定三列（SKILL 规范）。"""
    md = _merge_header_continuations(md)
    return "\n".join(_parse_header_line(line) or line for line in md.splitlines())


def preprocess_markdown(md_text: str, base_dir: Path) -> tuple[str, bool, str]:
    """解析图片、剥离照片 Markdown 行、转换表头行。"""
    md = sanitize_export_placeholders(md_text)
    md = transform_contact_header(md)
    md = resolve_image_paths(md, base_dir)
    has_photo = False
    photo_html = ""
    photo_match = re.search(r"!\[个人照片\]\((data:[^)]+)\)", md)
    if photo_match:
        has_photo = True
        photo_html = (
            f'<p class="photo"><img src="{photo_match.group(1)}" alt="个人照片" /></p>'
        )
        md = re.sub(r"!\[个人照片\]\([^)]+\)\s*\n?", "", md, count=1)
    elif re.search(r"!\[个人照片\]\(", md):
        md = re.sub(r"!\[个人照片\]\([^)]+\)\s*\n?", "", md, count=1)
    md = transform_header_rows(md)
    return md, has_photo, photo_html


def inject_photo_box(body_html: str, photo_html: str) -> str:
    """照片插在姓名/联系方式之后，绝对定位右上角，不占正文流。"""
    if not photo_html:
        return body_html
    m = re.search(
        r"(<h1[^>]*>.*?</h1>\s*(?:<p[^>]*>.*?</p>\s*)*)",
        body_html,
        flags=re.DOTALL,
    )
    if m:
        pos = m.end()
        return body_html[:pos] + photo_html + body_html[pos:]
    return photo_html + body_html


def _rectangles_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    return right - left > 0.5 and bottom - top > 0.5


def validate_pdf_photo_layout(pdf_path: Path) -> list[str]:
    """检测导出 PDF 中照片是否与文字块重叠（对齐 resume-tailor 审核）。"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []

    try:
        document = fitz.open(str(pdf_path))
        image_blocks: list[tuple[int, tuple[float, float, float, float]]] = []
        text_blocks: list[tuple[int, tuple[float, float, float, float]]] = []

        for page_index, page in enumerate(document, start=1):
            for block in page.get_text("dict").get("blocks", []):
                bbox = tuple(float(v) for v in block.get("bbox", ()))
                if len(bbox) != 4:
                    continue
                if block.get("type") == 1:
                    image_blocks.append((page_index, bbox))
                elif block.get("type") == 0:
                    text = "".join(
                        span.get("text", "")
                        for line in block.get("lines", [])
                        for span in line.get("spans", [])
                    )
                    if text.strip():
                        text_blocks.append((page_index, bbox))

        if not image_blocks:
            return []
        if len(image_blocks) != 1:
            return [
                f"PDF 中检测到 {len(image_blocks)} 张图片，应仅含 1 张个人照片。"
            ]

        image_page, image_bbox = image_blocks[0]
        for text_page, text_bbox in text_blocks:
            if image_page == text_page and _rectangles_overlap(image_bbox, text_bbox):
                return ["个人照片与简历正文重叠，请调整照片位置或大小后重新导出。"]
        return []
    except Exception as exc:
        return [f"无法校验 PDF 照片排版: {exc}"]


def md_to_html(md_text: str, base_dir: Path | None = None, preset: str = "standard") -> str:
    base = base_dir or Path(".")
    md, has_photo, photo_html = preprocess_markdown(md_text, base)
    body = markdown.markdown(md, extensions=["extra", "sane_lists"])
    body = inject_photo_box(body, photo_html)
    cfg = PRESETS.get(preset, PRESETS["standard"])
    body_class = ' class="has-photo"' if has_photo else ""
    return HTML_TEMPLATE.format(
        margin_bottom=cfg.get("margin_bottom", "0.8cm"),
        line_height=FIXED_LINE_HEIGHT,
        body_padding_top=cfg.get("body_padding_top", "0"),
        photo_reserve=PHOTO_RESERVE_PT,
        section_margin=cfg["section_margin"],
        h2_after=cfg["h2_after"],
        item_spacing=cfg["item_spacing"],
        body=body,
        body_class=body_class,
    )


async def export_async(input_md: Path, output_pdf: Path, preset: str = "standard"):
    from playwright.async_api import async_playwright

    md_text = input_md.read_text(encoding="utf-8")
    html_str = md_to_html(md_text, base_dir=input_md.parent, preset=preset)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_str, wait_until="load")
        await page.pdf(
            path=str(output_pdf),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        await browser.close()


def check_page_count(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def main():
    parser = argparse.ArgumentParser(description="Markdown → A4 单页 PDF（Playwright）")
    parser.add_argument("input", type=Path, help="输入 Markdown 文件")
    parser.add_argument("-o", "--output", type=Path, help="输出 PDF 路径")
    parser.add_argument(
        "--mode",
        choices=["standard", "diff"],
        default="standard",
        help="standard=标准, diff=保留 <ins>/<del> 标签",
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        default="standard",
        help="排版预设：standard / tight / fill",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"输入文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.input.with_suffix(".pdf")
    output.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(export_async(args.input, output, preset=args.preset))

    pages = check_page_count(output)
    photo_errors = validate_pdf_photo_layout(output)
    if photo_errors:
        for err in photo_errors:
            print(err, file=sys.stderr)
        print("Skill check: failed (photo layout).", file=sys.stderr)
        sys.exit(3)

    if pages == 1:
        print("Page check: 1 page.")
        print("Skill check: passed.")
        print(f"Exported: {output}")
        sys.exit(0)
    else:
        print(f"Page check: {pages} pages (expected 1).", file=sys.stderr)
        print("Skill check: failed.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
