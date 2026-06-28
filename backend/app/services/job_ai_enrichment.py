"""AI 批量解析/打标签：仅对 weak 岗位兜底，带内容 hash 缓存。"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from app.config import settings
from app.services.llm_client import client
from app.services.llm_priority import wait_for_studio_idle

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "ai_cache" / "job_parse"
EXTRACT_BATCH_SIZE = 10
TAG_BATCH_SIZE = 20

EXTRACT_SYSTEM = """你是校招岗位结构化解析助手。输入为若干条从网页抓取的脏文本。
输出 JSON（仅此 JSON，无 markdown）：
{
  "items": [
    {
      "index": 0,
      "is_job": true,
      "company": "用人单位",
      "role": "岗位或批次名",
      "cities": ["北京"],
      "job_type": "秋招|春招|实习|校招",
      "deadline": "",
      "summary": "一句话摘要≤40字",
      "tags": ["职能标签", "行业标签"],
      "reject_reason": ""
    }
  ]
}
规则：资讯/导航/版权/活动安排等非招聘岗位 is_job=false；company 不能是大学名除非该校直招。"""

TAG_SYSTEM = """为校招岗位批量打标准化标签。输入 JSON 岗位列表，输出：
{"items":[{"index":0,"tags":["后端","互联网","北京","本科","秋招"],"summary":"一句话亮点"}]}
标签从：职能、行业、城市、学历、类型、远程 等维度选 3-6 个。"""

WEAK_COMPANIES = frozenset(
    {"招聘单位待确认", "待确认公司", "未知企业", "—", ""}
)


def _cache_key(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load_cache(key: str) -> dict | None:
    p = CACHE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def needs_ai_enrichment(job: dict) -> bool:
    if job.get("validation_status") == "invalid":
        return True
    if job.get("validation_status") == "weak":
        return True
    company = (job.get("company") or "").strip()
    if company in WEAK_COMPANIES:
        return True
    if not job.get("jd_url") and len((job.get("jd_text") or "")) < 30:
        return True
    if job.get("ai_summary") and job.get("ai_tags"):
        return False
    return False


def needs_ai_tags(job: dict) -> bool:
    if job.get("validation_status") == "invalid":
        return False
    existing = set(job.get("ai_tags") or [])
    if len(existing) >= 3 and job.get("ai_summary"):
        return False
    return job.get("validation_status") in ("ok", "weak")


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _extract_batch(batch: list[dict]) -> list[dict]:
    lines = []
    for i, job in enumerate(batch):
        lines.append(
            {
                "index": i,
                "text": (job.get("jd_text") or job.get("role") or "")[:280],
                "source": job.get("source", ""),
                "channel": job.get("channel", ""),
            }
        )
    payload = json.dumps(lines, ensure_ascii=False)
    key = _cache_key("extract:" + payload)
    cached = _load_cache(key)
    if cached and "items" in cached:
        return cached["items"]

    if not settings.deepseek_api_key:
        return []

    for attempt, size in enumerate([len(batch), max(1, len(batch) // 2)]):
        chunk = batch[:size]
        if not chunk:
            continue
        sub_lines = lines[:size]
        sub_payload = json.dumps(sub_lines, ensure_ascii=False)
        try:
            data = await client.chat_json(
                EXTRACT_SYSTEM, sub_payload, temperature=0.1, max_tokens=4096
            )
            items = data.get("items") or []
            _save_cache(key, {"items": items})
            return items
        except Exception:
            if attempt == 0 and size > 1:
                logger.warning("ai extract batch failed, retry smaller size=%s", size)
                continue
            logger.exception("ai job extract batch failed")
            return []
    return []


async def _tag_batch(batch: list[dict]) -> list[dict]:
    brief = [
        {
            "index": i,
            "company": j.get("company"),
            "role": j.get("role"),
            "job_type": j.get("job_type"),
            "cities": j.get("locations") or [],
            "jd": (j.get("jd_text") or "")[:200],
        }
        for i, j in enumerate(batch)
    ]
    payload = json.dumps(brief, ensure_ascii=False)
    key = _cache_key("tag:" + payload)
    cached = _load_cache(key)
    if cached and "items" in cached:
        return cached["items"]

    if not settings.deepseek_api_key:
        return []

    try:
        data = await client.chat_json(TAG_SYSTEM, payload, temperature=0.15, max_tokens=3000)
        items = data.get("items") or []
        _save_cache(key, {"items": items})
        return items
    except Exception:
        logger.exception("ai job tag batch failed")
        return []


def _merge_extract(job: dict, item: dict) -> dict:
    if not item.get("is_job"):
        job = {**job, "validation_status": "invalid", "validation_issues": [item.get("reject_reason") or "AI判定非岗位"]}
        return job
    out = dict(job)
    if item.get("company") and item["company"] not in WEAK_COMPANIES:
        out["company"] = re.sub(r"\s+", "", str(item["company"]))[:60]
    if item.get("role"):
        out["role"] = str(item["role"])[:100]
    if item.get("cities"):
        out["locations"] = list(dict.fromkeys(item["cities"]))[:6]
        if out["locations"]:
            out["location"] = out["locations"][0]
    if item.get("job_type"):
        out["job_type"] = str(item["job_type"])[:20]
    if item.get("deadline"):
        out["deadline"] = str(item["deadline"])[:40]
    if item.get("summary"):
        out["ai_summary"] = str(item["summary"])[:120]
    ai_tags = list(item.get("tags") or [])
    if ai_tags:
        out["ai_tags"] = ai_tags
        merged_tags = list(dict.fromkeys((out.get("tags") or []) + ai_tags))
        out["tags"] = merged_tags[:12]
    if out.get("company") not in WEAK_COMPANIES and out.get("jd_url"):
        out["validation_status"] = "ok"
        out["validation_issues"] = []
    elif out.get("validation_status") != "invalid":
        out["validation_status"] = "weak"
    return out


def _merge_tags(job: dict, item: dict) -> dict:
    out = dict(job)
    tags = list(dict.fromkeys((out.get("tags") or []) + (item.get("tags") or [])))
    out["tags"] = tags[:12]
    out["ai_tags"] = list(item.get("tags") or out.get("ai_tags") or [])
    if item.get("summary") and not out.get("ai_summary"):
        out["ai_summary"] = str(item["summary"])[:120]
    return out


async def enrich_jobs(jobs: list[dict]) -> tuple[list[dict], dict]:
    """对 weak 岗位批量 AI 解析 + 对 ok 岗位批量打标签。返回 (jobs, stats)。"""
    stats = {"extract_batches": 0, "tag_batches": 0, "enriched": 0, "tagged": 0, "rejected": 0}
    if not settings.deepseek_api_key:
        return jobs, stats

    by_id = {j.get("id"): dict(j) for j in jobs if j.get("id")}
    extract_candidates = [j for j in jobs if needs_ai_enrichment(j)]
    for batch in _chunk(extract_candidates, EXTRACT_BATCH_SIZE):
        await wait_for_studio_idle()
        items = await _extract_batch(batch)
        stats["extract_batches"] += 1
        for item in items:
            idx = int(item.get("index", -1))
            if idx < 0 or idx >= len(batch):
                continue
            jid = batch[idx].get("id")
            if not jid or jid not in by_id:
                continue
            merged = _merge_extract(by_id[jid], item)
            by_id[jid] = merged
            stats["enriched"] += 1
            if merged.get("validation_status") == "invalid":
                stats["rejected"] += 1

    tag_candidates = [by_id[j["id"]] for j in jobs if j.get("id") in by_id and needs_ai_tags(by_id[j["id"]])]
    for batch in _chunk(tag_candidates, TAG_BATCH_SIZE):
        await wait_for_studio_idle()
        items = await _tag_batch(batch)
        stats["tag_batches"] += 1
        for item in items:
            idx = int(item.get("index", -1))
            if idx < 0 or idx >= len(batch):
                continue
            jid = batch[idx].get("id")
            if not jid or jid not in by_id:
                continue
            by_id[jid] = _merge_tags(by_id[jid], item)
            stats["tagged"] += 1

    return [by_id.get(j.get("id"), j) for j in jobs], stats


RERANK_SYSTEM = """你是校招顾问。根据用户偏好对岗位 Top 列表复核排序。
输出 JSON：{"ranked":[{"job_id":"...","priority":"P0|P1|P2","reason":"≤30字","summary":"一句话"}]}
只能使用输入中的 job_id，按匹配度降序。"""


async def ai_rerank_picks(prefs: dict, picks: list[dict], resume_hint: str = "") -> list[dict]:
    """对 digest Top-K 做 AI 精排（仅当 API key 可用）。"""
    if not settings.deepseek_api_key or not picks:
        return picks
    brief = [
        {
            "job_id": p["job_id"],
            "company": p["company"],
            "role": p["role"],
            "score": p.get("score"),
            "reasons": p.get("reasons"),
        }
        for p in picks[:12]
    ]
    user = json.dumps(
        {"preferences": prefs, "resume_hint": resume_hint[:500], "jobs": brief},
        ensure_ascii=False,
    )
    try:
        data = await client.chat_json(RERANK_SYSTEM, user, temperature=0.2, max_tokens=1200)
        ranked = {r["job_id"]: r for r in (data.get("ranked") or []) if r.get("job_id")}
        out = []
        for p in picks:
            r = ranked.get(p["job_id"])
            if not r:
                out.append(p)
                continue
            merged = dict(p)
            if r.get("priority") in ("P0", "P1", "P2"):
                merged["priority"] = r["priority"]
            if r.get("reason"):
                merged["reasons"] = [r["reason"]] + (merged.get("reasons") or [])[:2]
            if r.get("summary"):
                merged["ai_summary"] = r["summary"]
            out.append(merged)
        order = {r["job_id"]: i for i, r in enumerate(data.get("ranked") or []) if r.get("job_id")}
        out.sort(key=lambda x: order.get(x["job_id"], 999))
        return out
    except Exception:
        logger.exception("ai rerank picks failed")
        return picks
