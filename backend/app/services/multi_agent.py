"""多 Agent 编排：由动态 Planner 按步选择 specialist，无固定 PHASE_PIPELINE。"""
from __future__ import annotations

from typing import AsyncGenerator

from app.models.schemas import Session
from app.services.dynamic_agent import stream_dynamic_agent


async def stream_multi_agent_run(
    sess: Session,
    goal: str,
    *,
    auto_finalize: bool = False,
    confirmed: bool = False,
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
        if event.get("type") == "done":
            event["multi_agent"] = True
        yield event
