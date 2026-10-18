"""Windows 兼容启动：在创建事件循环前设置 Proactor 策略。

读取 backend/.env 中的 HOST / PORT / DEBUG，避免配置项写了却不生效。
"""
from __future__ import annotations

import asyncio
import sys


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    import uvicorn

    from app.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=["app"],
    )


if __name__ == "__main__":
    main()
