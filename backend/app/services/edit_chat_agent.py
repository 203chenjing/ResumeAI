"""编辑页对话 Agent：委托动态 Planner，无正则意图表。"""
from __future__ import annotations

from typing import AsyncGenerator

from app.models.schemas import Session
from app.services.dynamic_agent import stream_dynamic_agent


async def stream_edit_chat(
    sess: Session,
    user_message: str,
    *,
    client_id: str = "default",
    confirmed_action: dict | None = None,
    ui_context: dict | None = None,
) -> AsyncGenerator[dict, None]:
    async for event in stream_dynamic_agent(
        sess,
        user_message=user_message,
        client_id=client_id,
        mode="chat",
        confirmed_action=confirmed_action,
        ui_context=ui_context,
    ):
        yield event
