"""个人照片裁剪（540×790，与 tools/crop_profile_photo.py / SKILL 一致）。"""
import io

from PIL import Image, ImageOps

TARGET_W = 540
TARGET_H = 790
TARGET_RATIO = TARGET_W / TARGET_H


def crop_to_ratio(img: Image.Image, padding_ratio: float = 0.03) -> Image.Image:
    """居中裁切到 540:790，加安全边距，缩放到 540×790。"""
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    w, h = img.size
    cur_ratio = w / h
    if cur_ratio > TARGET_RATIO:
        new_w = int(h * TARGET_RATIO)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / TARGET_RATIO)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    if padding_ratio > 0:
        pw = int(img.size[0] * padding_ratio)
        ph = int(img.size[1] * padding_ratio)
        canvas = Image.new("RGBA", (img.size[0] + 2 * pw, img.size[1] + 2 * ph), (255, 255, 255, 0))
        canvas.paste(img, (pw, ph))
        img = canvas

    return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)


def crop_image_bytes(file_bytes: bytes, padding_ratio: float = 0.03) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    cropped = crop_to_ratio(img, padding_ratio=padding_ratio)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()
