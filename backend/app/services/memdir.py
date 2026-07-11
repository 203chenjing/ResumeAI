"""L4 长期记忆：memdir 分层知识库 + MEMORY.md 全局索引。"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "memdir"
TEMPLATE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "memory"

INDEX_MAX_LINES = 200
INDEX_MAX_BYTES = 25_600


def _client_dir(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DATA_ROOT / safe


def _topics_dir(client_id: str) -> Path:
    return _client_dir(client_id) / "topics"


def _index_path(client_id: str) -> Path:
    return _client_dir(client_id) / "MEMORY.md"


def _dream_state_path(client_id: str) -> Path:
    return _client_dir(client_id) / ".dream-state.json"


def _lock_path(client_id: str) -> Path:
    return _client_dir(client_id) / ".consolidate-lock"


def ensure_memdir(client_id: str = "default") -> Path:
    """初始化 memdir 目录结构；首次从仓库 memory/ 模板复制。"""
    root = _client_dir(client_id)
    topics = _topics_dir(client_id)
    root.mkdir(parents=True, exist_ok=True)
    topics.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)

    index = _index_path(client_id)
    if not index.exists() and TEMPLATE_ROOT.exists():
        template_index = TEMPLATE_ROOT / "MEMORY.md"
        if template_index.exists():
            index.write_text(template_index.read_text(encoding="utf-8"), encoding="utf-8")
        template_topics = TEMPLATE_ROOT / "topics"
        if template_topics.is_dir():
            for f in template_topics.glob("*.md"):
                dest = topics / f.name
                if not dest.exists():
                    dest.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    elif not index.exists():
        index.write_text(
            "# ResumeAI Memory Index\n\n- [knowledge-base.md](topics/knowledge-base.md): 用户经历素材\n",
            encoding="utf-8",
        )
    return root


def read_index(client_id: str = "default") -> str:
    ensure_memdir(client_id)
    return _index_path(client_id).read_text(encoding="utf-8")


def list_topics(client_id: str = "default") -> list[dict]:
    ensure_memdir(client_id)
    topics = []
    for f in sorted(_topics_dir(client_id).glob("*.md")):
        stat = f.stat()
        topics.append({
            "name": f.stem,
            "path": f"topics/{f.name}",
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return topics


def read_topic(client_id: str, topic_name: str) -> str:
    ensure_memdir(client_id)
    safe = re.sub(r"[^\w\-]", "", topic_name)
    path = _topics_dir(client_id) / f"{safe}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_topic(client_id: str, topic_name: str, content: str) -> None:
    ensure_memdir(client_id)
    safe = re.sub(r"[^\w\-]", "", topic_name)
    path = _topics_dir(client_id) / f"{safe}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    _ensure_index_pointer(client_id, safe, _topic_description(content))


def _topic_description(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "用户知识主题"


def _ensure_index_pointer(client_id: str, topic_name: str, description: str) -> None:
    index = _index_path(client_id)
    text = index.read_text(encoding="utf-8")
    pointer = f"- [{topic_name}.md](topics/{topic_name}.md): {description}"
    pattern = re.compile(rf"- \[{re.escape(topic_name)}\.md\]", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(pointer.split("]")[0] + f"](topics/{topic_name}.md): {description}", text, count=1)
    else:
        text = text.rstrip() + "\n" + pointer + "\n"
    _write_index_safe(client_id, text)


def _write_index_safe(client_id: str, text: str) -> None:
    lines = text.splitlines()
    if len(lines) > INDEX_MAX_LINES:
        text = "\n".join(lines[:INDEX_MAX_LINES]) + "\n\n<!-- truncated: move detail into topic files -->\n"
    encoded = text.encode("utf-8")
    if len(encoded) > INDEX_MAX_BYTES:
        text = encoded[:INDEX_MAX_BYTES].decode("utf-8", errors="ignore")
    _index_path(client_id).write_text(text, encoding="utf-8")


def sync_from_user_memory(client_id: str, payload: dict) -> None:
    """将 user_memory JSON 双写到 memdir topics。"""
    ensure_memdir(client_id)
    kb = (payload.get("knowledge_base_md") or "").strip()
    if kb:
        write_topic(client_id, "knowledge-base", f"---\ntype: knowledge\n---\n\n{kb}")
    prefs = payload.get("preferences") or {}
    if prefs:
        lines = ["---", "type: preferences", "---", "", "# 用户偏好", ""]
        for k, v in prefs.items():
            lines.append(f"- {k}: {v}")
        write_topic(client_id, "preferences", "\n".join(lines))
    notes = (payload.get("notes") or "").strip()
    if notes:
        write_topic(client_id, "notes", f"# 备注\n\n{notes}")
    job_prefs = payload.get("job_preferences")
    if job_prefs:
        write_topic(
            client_id,
            "job-targets",
            "---\ntype: job-targets\n---\n\n# 求职偏好\n\n```json\n"
            + json.dumps(job_prefs, ensure_ascii=False, indent=2)
            + "\n```\n",
        )


def load_for_prompt(client_id: str = "default", max_topic_chars: int = 1200) -> str:
    """拼装 L4 记忆注入 Planner 的文本块。"""
    ensure_memdir(client_id)
    parts = ["==== L4 长期记忆（memdir）====", read_index(client_id).strip()]
    for topic in ("knowledge-base", "preferences"):
        body = read_topic(client_id, topic)
        if body.strip():
            parts.append(f"\n--- {topic} ---\n{body.strip()[:max_topic_chars]}")
    parts.append("==== L4 结束 ====")
    return "\n".join(parts)


def get_dream_state(client_id: str) -> dict:
    ensure_memdir(client_id)
    path = _dream_state_path(client_id)
    if not path.exists():
        return {
            "last_consolidation_at": None,
            "sessions_since_consolidation": 0,
            "total_consolidations": 0,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"last_consolidation_at": None, "sessions_since_consolidation": 0, "total_consolidations": 0}


def save_dream_state(client_id: str, state: dict) -> None:
    ensure_memdir(client_id)
    _dream_state_path(client_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def increment_session_count(client_id: str) -> int:
    state = get_dream_state(client_id)
    state["sessions_since_consolidation"] = state.get("sessions_since_consolidation", 0) + 1
    save_dream_state(client_id, state)
    return state["sessions_since_consolidation"]


def acquire_consolidation_lock(client_id: str) -> bool:
    ensure_memdir(client_id)
    lock = _lock_path(client_id)
    if lock.exists():
        try:
            age_min = (datetime.now().timestamp() - lock.stat().st_mtime) / 60
            if age_min < 60:
                return False
        except OSError:
            pass
    lock.write_text(str(datetime.now().isoformat()), encoding="utf-8")
    return True


def release_consolidation_lock(client_id: str) -> None:
    lock = _lock_path(client_id)
    if lock.exists():
        lock.unlink(missing_ok=True)
