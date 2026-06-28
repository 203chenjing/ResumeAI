"""评测 runner：用固定数据的 CopilotContext 驱动选岗 Copilot，捕获工具调用与产出。

返回 RunResult，供 deepeval / 离线断言消费。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.services import career_copilot
from app.services.copilot_tools import CopilotContext
from evals.golden_dataset import FIXTURE_JOBS, FIXTURE_PREFS, FIXTURE_RESUME


@dataclass
class RunResult:
    reply: str = ""
    tools_used: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)

    @property
    def tool_names(self) -> list[str]:
        return [t.get("name", "") for t in self.tools_used]

    @property
    def block_types(self) -> list[str]:
        return [b.get("type", "") for b in self.blocks]


def make_fixture_context(
    *,
    jobs: list[dict] | None = None,
    resume: str | None = None,
    prefs: dict | None = None,
) -> CopilotContext:
    """构造数据固定的上下文，避免读库、保证评测可复现。"""
    return CopilotContext(
        client_id="eval",
        _jobs=list(jobs if jobs is not None else FIXTURE_JOBS),
        _resume=resume if resume is not None else FIXTURE_RESUME,
        _prefs=dict(prefs if prefs is not None else FIXTURE_PREFS),
    )


async def run_copilot_async(message: str, ctx: CopilotContext | None = None) -> RunResult:
    ctx = ctx or make_fixture_context()
    result = RunResult()
    async for ev in career_copilot._stream_with_tools("eval", message, history=None, ctx=ctx):
        etype = ev.get("type")
        if etype == "done":
            result.reply = ev.get("reply", "")
            result.tools_used = ev.get("tools_used", []) or []
            result.blocks = ev.get("blocks", []) or []
    return result


def run_copilot(message: str, ctx: CopilotContext | None = None) -> RunResult:
    """同步封装，便于 pytest / deepeval 调用。"""
    return asyncio.run(run_copilot_async(message, ctx))
