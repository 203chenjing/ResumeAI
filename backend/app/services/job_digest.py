"""岗位 AI 摘要：偏好匹配 + 投递优先级（爬虫后自动生成）。"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services.job_ai_enrichment import ai_rerank_picks
from app.services.job_feed import list_jobs
from app.services.job_preferences import load_job_preferences
from app.services.llm_client import client
from app.services.master_resume import get_active_master
from app.services.multi_jd_compare import quick_match_score
from app.services.user_memory import load_memory

logger = logging.getLogger(__name__)

DIGEST_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "job_digest"

DIGEST_SYSTEM = """你是校招求职顾问。根据用户偏好与岗位列表，输出 JSON：
{
  "headline": "一句话结论（≤30字）",
  "summary": "2-4句：本次新增多少、最值得投的方向、行动建议",
  "action_tips": ["建议1", "建议2"]
}
要求：只推荐列表中存在的公司；优先说明 P0/P1 岗位；语气简洁务实。"""


def _digest_path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DIGEST_DIR / f"{safe}.json"


def load_digest(client_id: str) -> dict | None:
    p = _digest_path(client_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_digest(client_id: str, data: dict) -> dict:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    data["generated_at"] = datetime.now().isoformat()
    _digest_path(client_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _text_hit(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords if k)


def _score_job(job: dict, prefs: dict, resume_md: str, *, is_new: bool) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []
    company = job.get("company", "")
    role = job.get("role", "")
    jd = job.get("jd_text", "")
    blob = f"{company} {role} {jd}"

    if _text_hit(company, prefs.get("company_blocklist") or []):
        return 0, "已在屏蔽公司列表", ["已屏蔽"]

    if _text_hit(company, prefs.get("company_wishlist") or []):
        score += 28
        reasons.append("目标公司")

    if _text_hit(blob, prefs.get("target_roles") or []):
        score += 22
        reasons.append("岗位方向匹配")

    cities = job.get("locations") or []
    loc = job.get("location", "")
    city_blob = " ".join(cities + ([loc] if loc else []))
    if _text_hit(city_blob, prefs.get("target_cities") or []):
        score += 18
        reasons.append("工作地匹配")

    jt = job.get("job_type") or ""
    if jt and jt in (prefs.get("job_types") or []):
        score += 12
        reasons.append(f"类型·{jt}")

    if is_new:
        score += 10
        reasons.append("本次新增")

    if job.get("validation_status") == "ok":
        score += 5

    if resume_md.strip():
        match = quick_match_score(resume_md, jd or role, prefs=prefs)
        bonus = int(match.overall_score * 0.25)
        score += bonus
        if bonus >= 15:
            reasons.append(f"简历匹配约{match.overall_score}分")

    if not reasons:
        reasons.append("可观望")

    priority = "P2"
    if score >= 70:
        priority = "P0"
    elif score >= 45:
        priority = "P1"

    return score, priority, reasons[:4]


def _rule_summary(
    prefs: dict,
    new_count: int,
    picks: list[dict],
) -> dict:
    p0 = [p for p in picks if p["priority"] == "P0"]
    p1 = [p for p in picks if p["priority"] == "P1"]
    headline = f"新增 {new_count} 条，建议优先投 {len(p0)} 个"
    if not picks:
        headline = "暂无高匹配岗位，请完善偏好或刷新抓取"
    lines = []
    if new_count:
        lines.append(f"本次爬虫新增 {new_count} 条岗位。")
    if p0:
        top = "、".join(f"{p['company']}·{p['role']}" for p in p0[:3])
        lines.append(f"优先投递（P0）：{top}。")
    elif p1:
        top = "、".join(f"{p['company']}" for p in p1[:3])
        lines.append(f"次优先（P1）：{top}。")
    else:
        lines.append("可在下方列表按城市/类型筛选，或补充目标岗位与城市后重新生成摘要。")
    tips = []
    if not (prefs.get("target_roles") or prefs.get("target_cities")):
        tips.append("填写目标岗位与城市，摘要会更准")
    if p0:
        tips.append("P0 岗位建议 48 小时内投递并定制简历")
    if new_count:
        tips.append("新增岗位已标「新」，可先看再投")
    return {"headline": headline, "summary": " ".join(lines), "action_tips": tips[:3]}


async def _llm_polish(prefs: dict, new_count: int, picks: list[dict]) -> dict | None:
    if not settings.deepseek_api_key:
        return None
    brief = [
        {
            "id": p["job_id"],
            "company": p["company"],
            "role": p["role"],
            "priority": p["priority"],
            "reasons": p["reasons"],
            "is_new": p.get("is_new"),
        }
        for p in picks[:12]
    ]
    user = json.dumps(
        {
            "preferences": prefs,
            "new_count": new_count,
            "priority_jobs": brief,
        },
        ensure_ascii=False,
    )
    try:
        return await client.chat_json(DIGEST_SYSTEM, user, temperature=0.3)
    except Exception:
        logger.exception("job digest llm failed")
        return None


async def build_job_digest(
    client_id: str,
    *,
    new_job_ids: list[str] | None = None,
) -> dict:
    """生成并保存 AI 投递摘要。"""
    prefs = load_job_preferences(client_id)
    jobs = [j for j in list_jobs(client_id) if j.get("validation_status") != "invalid"]
    new_set = set(new_job_ids or [])

    resume_md = ""
    master = get_active_master(client_id)
    if master:
        resume_md = master.get("markdown", "")
    if not resume_md:
        resume_md = load_memory(client_id).get("knowledge_base_md", "")

    scored: list[dict] = []
    for job in jobs:
        is_new = job.get("id") in new_set
        score, priority, reasons = _score_job(job, prefs, resume_md, is_new=is_new)
        if score < 20 and not is_new:
            continue
        scored.append(
            {
                "job_id": job.get("id", ""),
                "company": job.get("company", ""),
                "role": job.get("role", ""),
                "job_type": job.get("job_type", ""),
                "locations": job.get("locations") or [],
                "priority": priority,
                "score": score,
                "reasons": reasons,
                "is_new": is_new,
                "jd_url": job.get("jd_url", ""),
                "ai_summary": job.get("ai_summary", ""),
            }
        )

    scored.sort(key=lambda x: (-x["score"], not x["is_new"]))
    picks = scored[:15]
    picks = await ai_rerank_picks(prefs, picks, resume_hint=resume_md[:500])
    new_count = len(new_set) if new_set else sum(1 for p in picks if p.get("is_new"))

    rule = _rule_summary(prefs, new_count, picks)
    llm = await _llm_polish(prefs, new_count, picks)
    headline = (llm or {}).get("headline") or rule["headline"]
    summary = (llm or {}).get("summary") or rule["summary"]
    action_tips = (llm or {}).get("action_tips") or rule["action_tips"]

    digest = {
        "headline": headline,
        "summary": summary,
        "action_tips": action_tips,
        "new_count": new_count,
        "priority_jobs": picks,
        "preferences_snapshot": prefs,
        "used_llm": bool(llm),
        "ai_reranked": bool(settings.deepseek_api_key),
    }
    return save_digest(client_id, digest)
