"""个人照片：上传裁剪、注入 Markdown、导出 staging。"""
import re
import shutil
from pathlib import Path

from app.services.photo_crop import TARGET_H, TARGET_W, crop_image_bytes

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = BACKEND_ROOT / "uploads"
PHOTO_FILENAME = "profile-photo.png"

PHOTO_LINE_RE = re.compile(r"!\[个人照片\]\([^)]+\)\s*\n?", re.MULTILINE)


def session_photo_dir(session_id: str) -> Path:
    return UPLOADS_DIR / session_id


def session_photo_path(session_id: str) -> Path:
    return session_photo_dir(session_id) / PHOTO_FILENAME


def photo_ref_for_session(session_id: str) -> str:
    """Markdown 中使用的相对路径（相对 backend 根目录）。"""
    return f"uploads/{session_id}/{PHOTO_FILENAME}"


def crop_profile_image(file_bytes: bytes, padding_ratio: float = 0.03) -> bytes:
    """裁剪到 540×790（复用 photo_crop，与 crop_profile_photo.py 一致）。"""
    return crop_image_bytes(file_bytes, padding_ratio=padding_ratio)


def save_session_photo(session_id: str, file_bytes: bytes, padding_ratio: float = 0.03) -> str:
    """裁剪并保存，返回 Markdown 引用路径。"""
    cropped = crop_profile_image(file_bytes, padding_ratio=padding_ratio)
    dest_dir = session_photo_dir(session_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = session_photo_path(session_id)
    dest.write_bytes(cropped)
    return photo_ref_for_session(session_id)


def delete_session_photo(session_id: str) -> None:
    path = session_photo_path(session_id)
    if path.exists():
        path.unlink()


def has_session_photo(session_id: str) -> bool:
    return session_photo_path(session_id).exists()


def apply_photo_to_markdown(md: str, photo_ref: str) -> str:
    """在联系方式之后、`## 教育经历` 之前注入照片行（对齐 resume-template / SKILL）。"""
    text = PHOTO_LINE_RE.sub("", md).strip() + "\n"
    if not photo_ref:
        return text
    photo_line = f"![个人照片]({photo_ref})"
    marker = "## 教育经历"
    if marker in text:
        return text.replace(marker, f"{photo_line}\n\n{marker}", 1)
    # 无教育经历标题时，尽量插在标题块之后
    if text.startswith("# "):
        parts = text.split("\n\n", 1)
        if len(parts) == 2:
            return f"{parts[0]}\n\n{photo_line}\n\n{parts[1]}"
    return text.rstrip() + f"\n\n{photo_line}\n"


def strip_photo_from_markdown(md: str) -> str:
    return PHOTO_LINE_RE.sub("", md).strip() + "\n"


def stage_photo_for_export(md: str, session_id: str, export_dir: Path) -> str:
    """复制照片到 exports 目录，并改写 Markdown 为同目录相对路径。"""
    src = session_photo_path(session_id)
    if not src.exists():
        return strip_photo_from_markdown(md)
    export_dir.mkdir(parents=True, exist_ok=True)
    dest = export_dir / PHOTO_FILENAME
    shutil.copy2(src, dest)
    md_with_photo = apply_photo_to_markdown(strip_photo_from_markdown(md), PHOTO_FILENAME)
    return md_with_photo
