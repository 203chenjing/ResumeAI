"""个人照片裁剪 CLI（逻辑与 app.services.photo_crop 一致）。

用法：
    python crop_profile_photo.py input.png
    python crop_profile_photo.py input.png -o output.png --padding-ratio 0.05
"""
import argparse
import sys
from pathlib import Path

# 允许从 backend/tools 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.services.photo_crop import TARGET_H, TARGET_W, crop_to_ratio  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=f"裁剪个人照片到 {TARGET_W}×{TARGET_H} px")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--padding-ratio", type=float, default=0.03)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.input.with_name(args.input.stem + "-cropped.png")
    img = Image.open(args.input).convert("RGBA")
    cropped = crop_to_ratio(img, padding_ratio=args.padding_ratio)
    cropped.save(output, "PNG")
    print(f"Saved: {output} ({TARGET_W}×{TARGET_H})")


if __name__ == "__main__":
    main()
