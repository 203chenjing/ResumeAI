"""将 knowledge/简历数据库.md 同步到 user_memory（default 客户端）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.user_memory import CANONICAL_KB_PATH, save_memory  # noqa: E402


def main() -> int:
    if not CANONICAL_KB_PATH.is_file():
        print(f"未找到知识库文件: {CANONICAL_KB_PATH}")
        return 1
    content = CANONICAL_KB_PATH.read_text(encoding="utf-8-sig").strip()
    if not content:
        print("知识库文件为空")
        return 1
    save_memory("default", {"knowledge_base_md": content})
    print(f"已写入 default 用户记忆，共 {len(content)} 字符")
    print(f"来源: {CANONICAL_KB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
