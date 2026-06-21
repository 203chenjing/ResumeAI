"""知识库待确认沉淀：对标 llm-wiki approval gate。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pending_knowledge"


def _path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return DATA_DIR / f"{safe}.json"


def _load(client_id: str) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(client_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(client_id: str, items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path(client_id).write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_pending_from_diff(
    *,
    client_id: str,
    source: str,
    original_text: str,
    new_text: str,
    context: str = "",
) -> dict | None:
    """从单条建议 diff 提取可沉淀条目（规则层，无 LLM）。"""
    if not new_text or new_text.strip() == original_text.strip():
        return None
    if len(new_text.strip()) < 8:
        return None

    entry = {
        "id": uuid.uuid4().hex[:12],
        "source": source,
        "context": context,
        "original_text": original_text[:500],
        "new_text": new_text[:800],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    items = _load(client_id)
    items.append(entry)
    _save(client_id, items)
    return entry


def list_pending(client_id: str, status: str | None = "pending") -> list[dict]:
    items = _load(client_id)
    if status:
        return [i for i in items if i.get("status") == status]
    return items


def confirm_pending(client_id: str, entry_id: str, action: str) -> dict:
    """action: confirm | ignore"""
    items = _load(client_id)
    found = None
    for i in items:
        if i.get("id") == entry_id:
            i["status"] = "confirmed" if action == "confirm" else "ignored"
            i["resolved_at"] = datetime.now().isoformat()
            found = i
            break
    if not found:
        raise ValueError("条目不存在")
    _save(client_id, items)
    return found


def merge_confirmed_into_kb(knowledge_md: str, client_id: str) -> str:
    """将已确认条目追加到知识库 Markdown 末尾。"""
    confirmed = [i for i in _load(client_id) if i.get("status") == "confirmed"]
    if not confirmed:
        return knowledge_md
    block = ["\n\n## 沉淀素材（待整理）\n"]
    for c in confirmed[-20:]:
        block.append(f"- [{c.get('source', 'edit')}] {c.get('new_text', '')[:200]}")
    return knowledge_md.rstrip() + "\n".join(block) + "\n"
