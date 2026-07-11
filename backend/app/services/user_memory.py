"""用户长期记忆：跨 JD / 跨会话复用知识库与偏好（本地文件存储）。"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "user_memory"
CANONICAL_KB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "简历数据库.md"
DEFAULT_CLIENT = "default"

DEFAULT_MEMORY = {
    "knowledge_base_md": "",
    "preferences": {
        "writing_style": "量化、STAR、强动词",
        "prefer_accept_safe": True,
        "remind_finalize": True,
        "review_policy": "accept_safe",
        "recent_intent": "",
    },
    "notes": "",
}

PREF_KEYS = frozenset({
    "writing_style",
    "prefer_accept_safe",
    "remind_finalize",
    "review_policy",
    "recent_intent",
    "notes",
})


def _path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or DEFAULT_CLIENT
    return DATA_DIR / f"{safe}.json"


def _load_canonical_kb() -> str:
    if CANONICAL_KB_PATH.is_file():
        try:
            text = CANONICAL_KB_PATH.read_text(encoding="utf-8-sig").strip()
            return text
        except Exception as e:
            logger.warning("read canonical kb failed: %s", e)
    return ""


def load_memory(client_id: str = DEFAULT_CLIENT) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(client_id)
    use_canonical = client_id == DEFAULT_CLIENT
    if not path.exists():
        merged = dict(DEFAULT_MEMORY)
        if use_canonical:
            kb = _load_canonical_kb()
            if kb:
                merged["knowledge_base_md"] = kb
        return merged
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_MEMORY)
        merged.update(data)
        if "preferences" in data:
            merged["preferences"] = {**DEFAULT_MEMORY["preferences"], **data["preferences"]}
        if use_canonical and not (merged.get("knowledge_base_md") or "").strip():
            kb = _load_canonical_kb()
            if kb:
                merged["knowledge_base_md"] = kb
        return merged
    except Exception as e:
        logger.warning("load_memory failed: %s", e)
        merged = dict(DEFAULT_MEMORY)
        if use_canonical:
            kb = _load_canonical_kb()
            if kb:
                merged["knowledge_base_md"] = kb
        return merged


def save_memory(client_id: str, payload: dict) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = load_memory(client_id)
    if "knowledge_base_md" in payload:
        current["knowledge_base_md"] = (payload.get("knowledge_base_md") or "").strip()
    if "preferences" in payload and isinstance(payload["preferences"], dict):
        current["preferences"] = {**current["preferences"], **payload["preferences"]}
    if "notes" in payload:
        current["notes"] = (payload.get("notes") or "").strip()
    if "job_preferences" in payload and isinstance(payload["job_preferences"], dict):
        from app.services.job_preferences import DEFAULT_JOB_PREFERENCES, load_job_preferences

        merged_prefs = load_job_preferences(client_id)
        for key in DEFAULT_JOB_PREFERENCES:
            if key in payload["job_preferences"]:
                merged_prefs[key] = payload["job_preferences"][key]
        current["job_preferences"] = merged_prefs
    _path(client_id).write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from app.services.memdir import sync_from_user_memory

        sync_from_user_memory(client_id, current)
    except Exception as e:
        logger.warning("memdir sync failed: %s", e)
    return current


def merge_preferences(client_id: str, updates: dict) -> dict:
    """合并 Planner 输出的偏好更新，返回实际写入的字段。"""
    if not updates:
        return {}
    filtered = {
        k: v
        for k, v in updates.items()
        if k in PREF_KEYS and v is not None and str(v).strip() != ""
    }
    if not filtered:
        return {}
    mem = load_memory(client_id)
    prefs = {**mem.get("preferences", {}), **{k: v for k, v in filtered.items() if k != "notes"}}
    if "review_policy" in filtered:
        prefs["prefer_accept_safe"] = filtered["review_policy"] == "accept_safe"
    if "notes" in filtered:
        mem["notes"] = str(filtered["notes"]).strip()
    mem["preferences"] = prefs
    save_memory(client_id, {"preferences": prefs, "notes": mem.get("notes", "")})
    return filtered


def memory_context_for_prompt(client_id: str = DEFAULT_CLIENT) -> str:
    try:
        from app.services.memdir import load_for_prompt

        return load_for_prompt(client_id)
    except Exception as e:
        logger.warning("memdir load_for_prompt failed, fallback to JSON: %s", e)
    mem = load_memory(client_id)
    kb = mem.get("knowledge_base_md", "")
    prefs = mem.get("preferences", {})
    parts = ["==== 用户长期记忆（跨 JD 复用）===="]
    if kb.strip():
        parts.append(f"知识库素材（摘要前 800 字）：\n{kb.strip()[:800]}")
    parts.append(f"写作偏好：{prefs.get('writing_style', '')}")
    parts.append(f"审阅策略 review_policy：{prefs.get('review_policy', 'accept_safe')}")
    if prefs.get("recent_intent"):
        parts.append(f"近期常用目标：{prefs.get('recent_intent')}")
    parts.append("==== 记忆结束 ====")
    return "\n".join(parts)
