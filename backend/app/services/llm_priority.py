"""改稿链路优先：爬虫 AI enrichment 在改稿进行中主动让路。"""
from __future__ import annotations

import asyncio

_studio_active = 0
_lock = asyncio.Lock()


def studio_active() -> bool:
    return _studio_active > 0


def studio_enter() -> None:
    global _studio_active
    _studio_active += 1


def studio_leave() -> None:
    global _studio_active
    _studio_active = max(0, _studio_active - 1)


async def wait_for_studio_idle(*, max_wait: float = 120.0, interval: float = 0.4) -> None:
    """爬虫 enrichment 批次间调用，改稿进行中则短暂等待。"""
    waited = 0.0
    while studio_active() and waited < max_wait:
        await asyncio.sleep(interval)
        waited += interval
