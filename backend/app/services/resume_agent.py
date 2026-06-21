"""Resume Agent：委托动态 Planner（保留 _done_event 供 router 复用）。"""
from __future__ import annotations

from typing import AsyncGenerator

from app.models.schemas import Session
from app.services.dynamic_agent import _done_event, stream_dynamic_agent


async def stream_agent_run(
    sess: Session,
    goal: str,
    *,
    auto_finalize: bool = False,
    use_llm_planner: bool = True,
    client_id: str = "default",
    confirmed_action: dict | None = None,
) -> AsyncGenerator[dict, None]:
    async for event in stream_dynamic_agent(
        sess,
        goal=goal,
        client_id=client_id,
        mode="orchestrate",
        auto_finalize=auto_finalize,
        confirmed_action=confirmed_action,
    ):
        yield event


__all__ = ["stream_agent_run", "_done_event"]
