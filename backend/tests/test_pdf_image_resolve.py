"""PDF 排版：图片内嵌与三列表头行。"""
from pathlib import Path

from tools.markdown_resume_to_pdf import (
    preprocess_markdown,
    resolve_image_paths,
    transform_header_rows,
)


def test_resolve_image_paths_embeds_base64(tmp_path):
    img = tmp_path / "profile-photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    md = "![个人照片](profile-photo.png)\n\n## 教育经历"
    out = resolve_image_paths(md, tmp_path)
    assert "data:image/png;base64," in out
    assert "profile-photo.png" not in out


def test_transform_contact_header_splits_role():
    from tools.markdown_resume_to_pdf import transform_contact_header

    md = "# 邱井晨\n\n**189** · a@b.com · 上海 · AI产品实习生\n\n## 教育经历"
    out = transform_contact_header(md)
    assert 'class="contact-line"' in out
    assert "189" in out and "上海" in out
    assert 'class="target-role"' in out
    assert "AI产品实习生" in out


def test_transform_header_rows_education_three_col():
    md = "**上海大学**  管理学院 · 硕士  2024.09-2027.05"
    out = transform_header_rows(md)
    assert "管理学院 · 硕士" in out
    assert "col-mid" in out
    assert "2024.09-2027.05" in out


def test_transform_header_rows_internship():
    md = "**携程公司**  AI 产品实习生  2025.12-至今"
    out = transform_header_rows(md)
    assert "resume-header-row" in out
    assert "resume-header-row--stacked" not in out
    assert "携程公司" in out
    assert "2025.12-至今" in out


def test_transform_header_rows_internship_long_company():
    md = "**携程计算机技术（上海）有限公司**  AI 搜索产品实习生  2025.12-至今"
    out = transform_header_rows(md)
    assert "resume-header-row--stacked" not in out
    assert "long-left" not in out
    assert "携程计算机技术（上海）有限公司" in out
    assert "AI 搜索产品实习生" in out
    assert "col-mid" in out


def test_transform_header_rows_company_with_spaces_no_wrap():
    md = "**携程计算机技术 (上海) 有限公司**  AI 搜索产品实习生  2025.12-至今"
    out = transform_header_rows(md)
    assert "携程计算机技术(上海)有限公司" in out
    assert "nowrap" not in out  # nowrap is CSS; company normalized in HTML


def test_merge_split_company_suffix_line():
    md = """**携程计算机技术**  AI 搜索产品实习生  2025.12-至今
(上海) 有限公司"""
    out = transform_header_rows(md)
    assert "携程计算机技术(上海)有限公司" in out
    assert "(上海) 有限公司" not in out or "携程计算机技术(上海)有限公司" in out


def test_sanitize_export_placeholders():
    from tools.markdown_resume_to_pdf import sanitize_export_placeholders

    md = "分析了[待补充：数量]条用户反馈"
    assert sanitize_export_placeholders(md) == "分析了若干条用户反馈"


def test_preprocess_strips_photo_and_injects_html(tmp_path):
    img = tmp_path / "profile-photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    md = "# 张三\n\n![个人照片](profile-photo.png)\n\n## 教育经历"
    processed, has_photo, photo_html = preprocess_markdown(md, tmp_path)
    assert has_photo is True
    assert 'class="photo"' in photo_html
    assert "![个人照片]" not in processed
    assert "个人照片" in photo_html


def test_check_markdown_spacing_detects_blank_lines():
    from tools.markdown_resume_to_pdf import check_markdown_spacing

    issues = check_markdown_spacing("## A\n\n\n\n\n## B")
    assert any("空行" in i for i in issues)

    tail_issues = check_markdown_spacing("## A\n内容\n\n\n")
    assert any("文末" in i for i in tail_issues)
