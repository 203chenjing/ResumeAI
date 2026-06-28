"""求职 Copilot：LUI + 声明式 GenUI（对标 Google A2UI 轻量实现）。"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncGenerator

from app.config import settings
from app.services.copilot_tools import TOOLS, CopilotContext, run_tool
from app.services.job_digest import load_digest
from app.services.job_feed import list_jobs
from app.services.job_preferences import load_job_preferences
from app.services.llm_client import client
from app.services.master_resume import get_active_master
from app.services.match_engine import rerank_jobs
from app.services.user_memory import load_memory

logger = logging.getLogger(__name__)

COPILOT_SYSTEM = """你是 ResumeAI 求职 Copilot。用户通过自然语言操控岗位发现页。
你可以调用工具获取数据，并用简短中文回复。不要编造不存在的公司。
回复风格：务实、像资深求职顾问，2-4 句为主。"""

COPILOT_TOOL_SYSTEM = """你是 ResumeAI 的「选岗 Copilot」，一位资深校招求职顾问。
你的任务：帮用户从岗位库里发现、筛选、匹配、对比岗位，给出可执行建议。

工作方式：
- 先用工具获取真实数据，再回答。绝不编造公司、岗位或匹配分。
- 「最适合我 / 推荐投哪个」→ rerank_by_resume；「今天有什么新岗位 / 优先级」→ get_daily_digest；
  指定城市/类型/公司检索 → search_jobs；「A 和 B 投哪个」→ compare_jobs；要看 JD 细节 → get_job_detail。
- 需要时可连续调用多个工具。拿到结果后，用 2-4 句中文给出务实结论，点名具体公司/岗位，并说明理由或下一步。
- 若工具返回 no_resume/no_digest 等错误，向用户解释并引导（卡片按钮已自动给出），不要强答。

当前用户情况：{profile}"""

MAX_TOOL_ITERS = 4


def _resume_for(client_id: str) -> str:
    master = get_active_master(client_id)
    if master:
        return master.get("markdown", "") or ""
    mem = load_memory(client_id)
    return mem.get("knowledge_base_md", "") or ""


def _job_card(job: dict, score: int | None = None) -> dict:
    return {
        "id": job.get("id", ""),
        "company": job.get("company", ""),
        "role": job.get("role", ""),
        "job_type": job.get("job_type", ""),
        "location": job.get("location", ""),
        "deadline": job.get("deadline", ""),
        "jd_url": job.get("jd_url", ""),
        "source": job.get("source", ""),
        "match_score": score,
    }


def _detect_intent(message: str) -> str:
    m = message.lower()
    if re.search(r"最匹配|推荐|适合我|投哪个|匹配度|rerank|排序", message):
        return "rerank"
    if re.search(r"新岗位|新增|今天| digest|摘要|优先级|p0", message, re.I):
        return "digest"
    if re.search(r"爬|抓取|同步|刷新|飞书", message):
        return "crawl_hint"
    if re.search(r"北京|上海|深圳|杭州|成都|武汉|西安|广州|秋招|实习|校招", message):
        return "filter"
    return "chat"


def _apply_text_filters(jobs: list[dict], message: str) -> list[dict]:
    cities = ("北京", "上海", "深圳", "杭州", "成都", "武汉", "西安", "广州", "南京", "苏州")
    types = ("秋招", "实习", "校招", "提前批", "春招", "补录")
    out = jobs
    for c in cities:
        if c in message:
            out = [
                j
                for j in out
                if c in (j.get("location") or "")
                or c in " ".join(j.get("locations") or [])
                or any(c in t for t in (j.get("tags") or []))
            ]
    for t in types:
        if t in message:
            out = [j for j in out if (j.get("job_type") or "") == t or t in (j.get("role") or "")]
    return out[:12]


async def _llm_reply(message: str, context: str) -> str:
    if not settings.deepseek_api_key or settings.deepseek_api_key == "DEMO_KEY":
        return context[:200] if context else "已根据你的问题更新了视图，可直接点岗位卡片操作。"
    try:
        return (
            await client.chat_text(
                COPILOT_SYSTEM,
                f"用户问题：{message}\n\n上下文数据：\n{context[:3000]}",
                max_tokens=400,
                temperature=0.4,
            )
        ).strip()[:500]
    except Exception as e:
        logger.warning("copilot llm fallback: %s", e)
        return context[:300] if context else "请尝试：「推荐最匹配的岗位」或「北京秋招有哪些」"


def _sanitize_history(history: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for h in (history or [])[-8:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content[:2000]})
    return out


async def _stream_with_tools(
    client_id: str,
    message: str,
    history: list[dict] | None,
    ctx: CopilotContext | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """DeepSeek tool-calling 选岗循环：模型自主调用只读工具，前端实时渲染 GenUI。

    ctx 可注入（评测时传入固定数据的 CopilotContext）。
    """
    ctx = ctx or CopilotContext(client_id)
    profile = (
        f"岗位库 {len(ctx.jobs)} 条；偏好城市 {ctx.prefs.get('target_cities') or '未设置'}；"
        f"母版简历：{'有' if ctx.resume_md.strip() else '无（无法做匹配重排）'}"
    )
    messages: list[dict] = [
        {"role": "system", "content": COPILOT_TOOL_SYSTEM.format(profile=profile)},
        *_sanitize_history(history),
        {"role": "user", "content": message},
    ]

    collected: list[dict] = []
    seen_block_keys: set[str] = set()
    tools_used: list[dict] = []
    final_reply = ""

    for _ in range(MAX_TOOL_ITERS):
        msg = await client.chat_with_tools(messages, TOOLS, max_tokens=700, temperature=0.3)
        tool_calls = msg.get("tool_calls") or []
        messages.append(
            {"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls}
            if tool_calls
            else {"role": "assistant", "content": msg.get("content") or ""}
        )
        if not tool_calls:
            final_reply = (msg.get("content") or "").strip()
            break

        for tc in tool_calls:
            fn = (tc.get("function") or {}).get("name", "")
            raw_args = (tc.get("function") or {}).get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            tools_used.append({"name": fn, "args": args})
            res = run_tool(ctx, fn, args)
            if res.get("thinking"):
                yield {"type": "thinking", "content": res["thinking"]}
            for block in res.get("blocks") or []:
                key = json.dumps(block, ensure_ascii=False, sort_keys=True)
                if key not in seen_block_keys:
                    seen_block_keys.add(key)
                    collected.append(block)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(res.get("result", {}), ensure_ascii=False)[:4000],
                }
            )
    else:
        final_reply = final_reply or "已检索多轮，建议换个问法，或直接点下方岗位卡片操作。"

    if not final_reply:
        final_reply = "我已更新右侧结果，可点岗位卡片改简历，或继续问『最适合我的岗位』。"

    yield {"type": "text", "content": final_reply}
    for block in collected:
        yield {"type": "gen_ui", "block": block}
    yield {
        "type": "done",
        "reply": final_reply,
        "blocks": collected,
        "intent": "tool_calling",
        "tools_used": tools_used,
    }


async def stream_career_copilot(
    client_id: str,
    message: str,
    *,
    history: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    message = (message or "").strip()
    if not message:
        yield {"type": "error", "message": "请输入问题"}
        return

    yield {"type": "thinking", "content": "分析意图…"}

    has_key = bool(settings.deepseek_api_key) and settings.deepseek_api_key != "DEMO_KEY"
    if has_key:
        try:
            async for ev in _stream_with_tools(client_id, message, history):
                yield ev
            return
        except Exception as e:
            logger.warning("copilot tool-calling fallback to heuristic: %s", e)
            yield {"type": "thinking", "content": "切换到本地规则模式…"}

    async for ev in _stream_heuristic(client_id, message, history=history):
        yield ev


async def _stream_heuristic(
    client_id: str,
    message: str,
    *,
    history: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    prefs = load_job_preferences(client_id)
    jobs = list_jobs(client_id, include_weak=False)
    resume_md = _resume_for(client_id)
    intent = _detect_intent(message)
    blocks: list[dict] = []
    context_lines: list[str] = []

    if intent == "rerank":
        if not resume_md.strip():
            blocks.append(
                {
                    "type": "actions",
                    "buttons": [
                        {"label": "去整理知识库", "action": "navigate", "payload": {"path": "/assets"}},
                        {"label": "上传简历改稿", "action": "navigate", "payload": {"path": "/studio/prepare"}},
                    ],
                }
            )
            reply = "还没有可用的母版简历。先去知识库或 Studio 上传简历，我才能算混合匹配分（BM25+技能图谱）。"
        else:
            ranked = rerank_jobs(resume_md, jobs, prefs=prefs, top_k=8)
            cards = [
                _job_card(r["job"], r["hybrid_score"])
                for r in ranked
            ]
            blocks.append(
                {
                    "type": "match_summary",
                    "headline": f"混合匹配 Top {len(cards)}",
                    "algorithm": "BM25×0.42 + 技能图谱×0.33 + Jaccard×0.25 + 偏好加权",
                    "top_scores": [
                        {"company": c["company"], "role": c["role"], "score": c["match_score"]}
                        for c in cards[:5]
                    ],
                }
            )
            blocks.append({"type": "job_cards", "jobs": cards})
            if cards:
                blocks.append(
                    {
                        "type": "actions",
                        "buttons": [
                            {
                                "label": "对比 Top3",
                                "action": "compare",
                                "payload": {"job_ids": [c["id"] for c in cards[:3]]},
                            }
                        ],
                    }
                )
            context_lines.append(f"Top1: {cards[0]['company']} {cards[0]['role']} {cards[0]['match_score']}分" if cards else "无岗位")
            reply = await _llm_reply(message, "\n".join(context_lines))

    elif intent == "digest":
        digest = load_digest(client_id)
        if digest:
            blocks.append(
                {
                    "type": "match_summary",
                    "headline": digest.get("headline", "岗位摘要"),
                    "summary": digest.get("summary", ""),
                    "top_scores": [
                        {
                            "company": p.get("company", ""),
                            "role": p.get("role", ""),
                            "score": p.get("score", 0),
                            "priority": p.get("priority", ""),
                        }
                        for p in (digest.get("priority_jobs") or [])[:5]
                    ],
                }
            )
            p0_cards = [
                _job_card(
                    next((j for j in jobs if j.get("id") == p.get("job_id")), {}),
                    p.get("score"),
                )
                for p in (digest.get("priority_jobs") or [])[:6]
                if p.get("priority") in ("P0", "P1")
            ]
            p0_cards = [c for c in p0_cards if c.get("company")]
            if p0_cards:
                blocks.append({"type": "job_cards", "jobs": p0_cards})
            context_lines.append(digest.get("summary", ""))
        else:
            blocks.append(
                {
                    "type": "actions",
                    "buttons": [{"label": "刷新岗位并生成摘要", "action": "crawl", "payload": {}}],
                }
            )
            context_lines.append("暂无 digest")
        reply = await _llm_reply(message, "\n".join(context_lines) or "请先生成岗位摘要")

    elif intent == "filter":
        filtered = _apply_text_filters(jobs, message)
        chips = []
        for c in ("北京", "上海", "深圳", "杭州", "秋招", "实习"):
            if c in message:
                chips.append({"label": c, "key": "filter", "value": c})
        if chips:
            blocks.append({"type": "filter_chips", "chips": chips})
        blocks.append({"type": "job_cards", "jobs": [_job_card(j) for j in filtered[:10]]})
        context_lines.append(f"筛选到 {len(filtered)} 条")
        reply = await _llm_reply(message, "\n".join(context_lines))

    elif intent == "crawl_hint":
        blocks.append(
            {
                "type": "actions",
                "buttons": [
                    {"label": "刷新全部来源", "action": "crawl", "payload": {}},
                ],
            }
        )
        reply = "可以点下面按钮触发抓取。我们比纯 GitHub 汇总表多了自动校验、去重和混合匹配重排。"

    else:
        # 通用对话：带岗位概况
        meta_count = len(jobs)
        context_lines.append(f"当前 feed {meta_count} 条；偏好城市 {prefs.get('target_cities')}")
        if resume_md.strip():
            top = rerank_jobs(resume_md, jobs, prefs=prefs, top_k=3)
            for r in top:
                j = r["job"]
                context_lines.append(f"- {j.get('company')} {j.get('role')} {r['hybrid_score']}分")
        reply = await _llm_reply(message, "\n".join(context_lines))

    yield {"type": "text", "content": reply}
    for block in blocks:
        yield {"type": "gen_ui", "block": block}
    yield {"type": "done", "reply": reply, "blocks": blocks, "intent": intent}
