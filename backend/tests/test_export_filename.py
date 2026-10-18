"""导出文件名收敛：防目录穿越与非法字符。"""
from pathlib import Path

from app.services.pdf_exporter import EXPORT_DIR, safe_export_filename


def test_keeps_normal_name():
    assert safe_export_filename("携程+邱井晨+产品实习.pdf") == "携程+邱井晨+产品实习.pdf"


def test_adds_pdf_suffix():
    assert safe_export_filename("简历") == "简历.pdf"


def test_strips_directory_traversal():
    assert safe_export_filename("../../.env") == "env.pdf"
    assert safe_export_filename("..\\..\\backend\\app\\config.py") == "config.py.pdf"


def test_absolute_path_is_flattened():
    assert safe_export_filename("C:\\Windows\\System32\\evil.pdf") == "evil.pdf"
    assert safe_export_filename("/etc/passwd") == "passwd.pdf"


def test_empty_falls_back_to_default():
    assert safe_export_filename("") == "resume.pdf"
    assert safe_export_filename("..") == "resume.pdf"


def test_result_stays_inside_export_dir():
    for raw in ("../../.env", "C:\\Windows\\evil.pdf", "a" * 300 + ".pdf"):
        path = (EXPORT_DIR / safe_export_filename(raw)).resolve()
        assert EXPORT_DIR.resolve() in path.parents
        assert path.name
        assert len(Path(path.name).name) <= 120
