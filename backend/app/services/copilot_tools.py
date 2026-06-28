"""选岗 Copilot 工具集：供 DeepSeek tool-calling 调用的纯后端只读工具。

每个工具返回 dict：
- result: 精简、可序列化的数据（喂回模型）
- blocks: 可选的 GenUI 区块（前端渲染卡片/摘要/按钮）
- thinking: 可选的进度提示（流式展示）

全部在仓内闭环，不依赖任何外部基建/OAuth。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.job_digest import load_digest
from app.services.job_feed import list_jobs
from app.services.job_preferences import load_job_preferences
from app.services.master_resume import get_active_master
from app.services.match_engine import rerank_jobs
from app.services.multi_jd_compare import compare_jobs as compare_jobs_engine
from app.services.user_memory import load_memory

MAX_CARDS = 12


TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": "按关键词/城市/类型/来源检索当前岗位库。用于『北京的后端实习』『字节有哪些岗位』这类查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "公司名或岗位关键词，可为空"},
                    "city": {"type": "string", "description": "工作城市，如 北京/上海/深圳，可为空"},
                    "job_type": {"type": "string", "description": "类型：实习/校招/秋招/春招/提前批，可为空"},
                    "source": {"type": "string", "description": "来源：github_joblist/ats_board/university_html 等，可为空"},
                    "limit": {"type": "integer", "description": "返回数量，默认 10，最大 12"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rerank_by_resume",
            "description": "用用户母版简历对岗位做混合匹配重排（BM25+技能图谱+Jaccard+偏好），回答『最适合我的/推荐投哪个』。需要简历。",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_k": {"type": "integer", "description": "返回 Top N，默认 6，最大 10"},
                    "city": {"type": "string", "description": "限定城市，可为空"},
                    "job_type": {"type": "string", "description": "限定类型，可为空"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_digest",
            "description": "获取今日岗位摘要与 P0/P1 优先级清单（含 AI 摘要）。回答『今天有什么新岗位/优先级』。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_jobs",
            "description": "对比多个岗位（按 job_id），输出各自匹配度与投递建议。回答『A 和 B 投哪个』。需要简历。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的岗位 id 列表，2-4 个",
                    }
                },
                "required": ["job_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_detail",
            "description": "按 job_id 获取单个岗位的完整信息（JD 正文、地点、截止、内推码）。",
            "parameters": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_preferences",
            "description": "获取用户求职偏好（目标城市/岗位类型/行业）以更好地推荐。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class CopilotContext:
    client_id: str
    _jobs: list[dict] | None = field(default=None, repr=False)
    _resume: str | None = field(default=None, repr=False)
    _prefs: dict | None = field(default=None, repr=False)

    @property
    def jobs(self) -> list[dict]:
        if self._jobs is None:
            self._jobs = list_jobs(self.client_id, include_weak=False)
        return self._jobs

    @property
    def resume_md(self) -> str:
        if self._resume is None:
            master = get_active_master(self.client_id)
            if master and master.get("markdown"):
                self._resume = master["markdown"]
            else:
                self._resume = load_memory(self.client_id).get("knowledge_base_md", "") or ""
        return self._resume

    @property
    def prefs(self) -> dict:
        if self._prefs is None:
            self._prefs = load_job_preferences(self.client_id)
        return self._prefs

    def job_by_id(self, job_id: str) -> dict | None:
        return next((j for j in self.jobs if j.get("id") == job_id), None)


def _card(job: dict, score: int | None = None) -> dict:
    return {
        "id": job.get("id", ""),
        "company": job.get("company", ""),
        "role": job.get("role", ""),
        "job_type": job.get("job_type", ""),
        "location": job.get("location", "") or "、".join(job.get("locations") or []),
        "deadline": job.get("deadline", ""),
        "jd_url": job.get("jd_url", ""),
        "source": job.get("source", ""),
        "referral_code": job.get("referral_code", ""),
        "match_score": score,
    }


def _compact(job: dict, score: int | None = None) -> dict:
    """喂回模型的精简表示（省 token）。"""
    return {
        "id": job.get("id", ""),
        "company": job.get("company", ""),
        "role": job.get("role", ""),
        "type": job.get("job_type", ""),
        "city": job.get("location", "") or "、".join(job.get("locations") or []),
        "score": score,
    }


def _filter_jobs(
    jobs: list[dict],
    *,
    query: str = "",
    city: str = "",
    job_type: str = "",
    source: str = "",
) -> list[dict]:
    out = jobs
    if query:
        q = query.lower()
        out = [
            j
            for j in out
            if q in (j.get("company") or "").lower()
            or q in (j.get("role") or "").lower()
            or q in (j.get("jd_text") or "").lower()
        ]
    if city:
        out = [
            j
            for j in out
            if city in (j.get("location") or "")
            or city in "、".join(j.get("locations") or [])
            or any(city in t for t in (j.get("tags") or []))
        ]
    if job_type:
        out = [
            j
            for j in out
            if job_type == (j.get("job_type") or "") or job_type in (j.get("role") or "")
        ]
    if source:
        out = [j for j in out if (j.get("source") or "") == source]
    return out


def run_tool(ctx: CopilotContext, name: str, args: dict) -> dict:
    args = args or {}
    if name == "search_jobs":
        limit = min(int(args.get("limit") or 10), MAX_CARDS)
        found = _filter_jobs(
            ctx.jobs,
            query=str(args.get("query") or "").strip(),
            city=str(args.get("city") or "").strip(),
            job_type=str(args.get("job_type") or "").strip(),
            source=str(args.get("source") or "").strip(),
        )
        top = found[:limit]
        blocks = [{"type": "job_cards", "jobs": [_card(j) for j in top]}] if top else []
        return {
            "result": {"total": len(found), "jobs": [_compact(j) for j in top]},
            "blocks": blocks,
            "thinking": f"检索到 {len(found)} 个岗位…",
        }

    if name == "rerank_by_resume":
        if not ctx.resume_md.strip():
            return {
                "result": {"error": "no_resume", "message": "用户尚无母版简历，无法做匹配重排"},
                "blocks": [
                    {
                        "type": "actions",
                        "buttons": [
                            {"label": "去整理知识库", "action": "navigate", "payload": {"path": "/assets"}},
                            {"label": "上传简历改稿", "action": "navigate", "payload": {"path": "/studio/prepare"}},
                        ],
                    }
                ],
            }
        top_k = min(int(args.get("top_k") or 6), 10)
        pool = _filter_jobs(
            ctx.jobs,
            city=str(args.get("city") or "").strip(),
            job_type=str(args.get("job_type") or "").strip(),
        )
        ranked = rerank_jobs(ctx.resume_md, pool, prefs=ctx.prefs, top_k=top_k)
        cards = [_card(r["job"], r["hybrid_score"]) for r in ranked]
        blocks = []
        if cards:
            blocks.append(
                {
                    "type": "match_summary",
                    "headline": f"混合匹配 Top {len(cards)}",
                    "summary": "BM25×0.42 + 技能图谱×0.33 + Jaccard×0.25 + 偏好加权",
                    "top_scores": [
                        {"company": c["company"], "role": c["role"], "score": c["match_score"]}
                        for c in cards[:5]
                    ],
                }
            )
            blocks.append({"type": "job_cards", "jobs": cards})
            blocks.append(
                {
                    "type": "actions",
                    "buttons": [
                        {"label": "对比 Top3", "action": "compare", "payload": {"job_ids": [c["id"] for c in cards[:3]]}}
                    ],
                }
            )
        return {
            "result": {"jobs": [_compact(r["job"], r["hybrid_score"]) for r in ranked]},
            "blocks": blocks,
            "thinking": "用你的简历做混合匹配重排…",
        }

    if name == "get_daily_digest":
        digest = load_digest(ctx.client_id)
        if not digest:
            return {
                "result": {"error": "no_digest", "message": "暂无今日摘要"},
                "blocks": [
                    {"type": "actions", "buttons": [{"label": "刷新岗位并生成摘要", "action": "crawl", "payload": {}}]}
                ],
            }
        priority = digest.get("priority_jobs") or []
        blocks = [
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
                    for p in priority[:5]
                ],
            }
        ]
        return {
            "result": {
                "headline": digest.get("headline", ""),
                "summary": digest.get("summary", ""),
                "priority": [
                    {"company": p.get("company"), "role": p.get("role"), "priority": p.get("priority"), "score": p.get("score")}
                    for p in priority[:6]
                ],
            },
            "blocks": blocks,
            "thinking": "读取今日摘要…",
        }

    if name == "compare_jobs":
        job_ids = [str(x) for x in (args.get("job_ids") or [])][:4]
        picked = [j for j in (ctx.job_by_id(i) for i in job_ids) if j]
        if len(picked) < 2:
            return {"result": {"error": "need_two", "message": "至少需要两个有效的 job_id 才能对比"}}
        if not ctx.resume_md.strip():
            return {
                "result": {"error": "no_resume"},
                "blocks": [{"type": "actions", "buttons": [{"label": "上传简历改稿", "action": "navigate", "payload": {"path": "/studio/prepare"}}]}],
            }
        rows = compare_jobs_engine(ctx.resume_md, picked, prefs=ctx.prefs)
        summary = [
            {
                "id": r.get("job_id"),
                "company": r.get("company"),
                "role": r.get("role"),
                "score": (r.get("match") or {}).get("overall_score"),
                "decision": (r.get("decision") or {}).get("level") if r.get("decision") else None,
            }
            for r in rows
        ]
        blocks = [
            {
                "type": "match_summary",
                "headline": f"对比 {len(rows)} 个岗位",
                "top_scores": [
                    {"company": s["company"], "role": s["role"], "score": s["score"]} for s in summary
                ],
            },
            {"type": "actions", "buttons": [{"label": "打开对比页", "action": "compare", "payload": {"job_ids": [r["job_id"] for r in rows]}}]},
        ]
        return {"result": {"comparison": summary}, "blocks": blocks, "thinking": "逐项对比匹配度与投递建议…"}

    if name == "get_job_detail":
        job = ctx.job_by_id(str(args.get("job_id") or ""))
        if not job:
            return {"result": {"error": "not_found"}}
        return {
            "result": {
                "id": job.get("id"),
                "company": job.get("company"),
                "role": job.get("role"),
                "type": job.get("job_type"),
                "city": job.get("location") or "、".join(job.get("locations") or []),
                "deadline": job.get("deadline"),
                "jd_url": job.get("jd_url"),
                "referral_code": job.get("referral_code"),
                "jd_text": (job.get("jd_text") or "")[:1200],
            },
            "blocks": [{"type": "job_cards", "jobs": [_card(job)]}],
        }

    if name == "get_preferences":
        p = ctx.prefs
        return {
            "result": {
                "target_roles": p.get("target_roles"),
                "target_cities": p.get("target_cities"),
                "job_types": p.get("job_types"),
                "company_wishlist": p.get("company_wishlist"),
                "company_blocklist": p.get("company_blocklist"),
                "extra_notes": p.get("extra_notes"),
            }
        }

    return {"result": {"error": "unknown_tool", "name": name}}
