"""Agent 编排 router（SSE）。"""
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatMessage
from app.services.agent_tools import execute_tool
from app.services.multi_agent import stream_multi_agent_run
from app.services.resume_agent import stream_agent_run
from app.services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent"])


class AgentRunRequest(BaseModel):
    session_id: str
    goal: str = Field(
        default="针对当前 JD 完成简历匹配分析、生成修改建议并智能审阅接受安全建议",
        max_length=2000,
    )
    jd_text: str = ""
    knowledge_base: str = ""
    auto_finalize: bool = False
    use_llm_planner: bool = True
    use_multi_agent: bool = True
    confirmed: bool = False
    confirmed_action: dict | None = None
    client_id: str = "default"


@router.post("/agent/run")
async def run_agent(payload: AgentRunRequest):
    sess = store.get(payload.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    if not sess.current_resume_md.strip():
        raise HTTPException(400, "请先上传并解析简历")
    if payload.jd_text.strip():
        sess.jd_text = payload.jd_text.strip()
    if payload.knowledge_base.strip():
        sess.knowledge_base_md = payload.knowledge_base.strip()
    if not sess.jd_text.strip():
        raise HTTPException(400, "请先粘贴 JD")
    store.update(sess)

    user_msg = ChatMessage(role="user", content=f"[Agent] {payload.goal}")
    sess.chat_history.append(user_msg)

    if payload.confirmed_action:
        async def confirm_only():
            action = payload.confirmed_action.get("action", "")
            action_input = payload.confirmed_action.get("action_input") or {}
            result = await execute_tool(
                sess, action, action_input, confirmed=True, client_id=payload.client_id
            )
            store.update(sess)
            from app.services.resume_agent import _done_event

            yield {
                "event": "message",
                "data": json.dumps(
                    {
                        "type": "done",
                        "summary": result.get("message") or "已确认执行",
                        "session": _done_event(sess, "操作完成").get("session"),
                    },
                    ensure_ascii=False,
                ),
            }

        return EventSourceResponse(confirm_only())

    async def event_generator():
        summary = ""
        try:
            runner = (
                stream_multi_agent_run(
                    sess,
                    payload.goal,
                    auto_finalize=payload.auto_finalize,
                    confirmed=payload.confirmed,
                    client_id=payload.client_id,
                    confirmed_action=payload.confirmed_action,
                )
                if payload.use_multi_agent
                else stream_agent_run(
                    sess,
                    payload.goal,
                    auto_finalize=payload.auto_finalize,
                    use_llm_planner=payload.use_llm_planner,
                    client_id=payload.client_id,
                    confirmed_action=payload.confirmed_action,
                )
            )
            async for event in runner:
                if event["type"] == "done":
                    summary = event.get("summary", "")
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False),
                }
        except Exception as e:
            logger.exception("agent stream error")
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False),
            }
            return

        sess.chat_history.append(ChatMessage(role="assistant", content=summary or "Agent 任务结束"))
        store.update(sess)

    return EventSourceResponse(event_generator())
