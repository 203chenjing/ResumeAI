"""知识库待确认沉淀：对标 llm-wiki approval gate。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pending_knowledge"
TEMPLATE_FIELDS = (
    "时间",
    "角色",
    "背景",
    "目标",
    "行动",
    "方法/工具",
    "协作对象",
    "结果",
    "量化指标",
    "可复用关键词",
    "可适配岗位",
    "证据/来源",
    "待确认",
)


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


def _extract_metrics(text: str) -> list[str]:
    metrics = re.findall(r"[^。；;\n]*(?:\d+(?:\.\d+)?%?|\d+\s*[个条项人次]|[一二三四五六七八九十]\s*轮)[^。；;\n]*", text)
    return [m.strip(" ，,。；;") for m in metrics if m.strip()][:5]


def _extract_keywords(text: str) -> list[str]:
    candidates = (
        "Python",
        "SQL",
        "LangChain",
        "Prompt",
        "PRD",
        "A/B",
        "badcase",
        "数据清洗",
        "知识图谱",
        "检索",
        "字段规范",
        "用户体验",
    )
    return [k for k in candidates if k.lower() in text.lower()][:8]


def _structured_facts(text: str, source: str) -> list[dict]:
    """把候选素材拆成固定字段，避免整句简历文案污染知识库。"""
    compact = " ".join((text or "").split()).strip()
    if not compact:
        return []

    facts: list[dict] = []
    metrics = _extract_metrics(compact)
    keywords = _extract_keywords(compact)
    if metrics:
        facts.append({"field": "量化指标", "value": "；".join(metrics)})
    if keywords:
        facts.append({"field": "可复用关键词", "value": "、".join(keywords)})

    field = "结果" if metrics else "行动"
    facts.append({"field": field, "value": compact[:300]})
    facts.append({"field": "证据/来源", "value": source})
    return facts


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
        "facts": _structured_facts(new_text, source),
        "target_title": "",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    items = _load(client_id)
    items.append(entry)
    _save(client_id, items)
    return entry


def list_pending(client_id: str, status: str | None = "pending") -> list[dict]:
    items = _load(client_id)
    for item in items:
        if not item.get("facts"):
            item["facts"] = _structured_facts(item.get("new_text", ""), item.get("source", "edit"))
        item.setdefault("target_title", "")
    if status:
        return [i for i in items if i.get("status") == status]
    return items


def confirm_pending(client_id: str, entry_id: str, action: str, target_title: str = "") -> dict:
    """action: confirm | ignore"""
    items = _load(client_id)
    found = None
    for i in items:
        if i.get("id") == entry_id:
            if action == "confirm":
                i["target_title"] = target_title.strip()
                if not i["target_title"]:
                    raise ValueError("请选择归属经历")
                if not i.get("facts"):
                    i["facts"] = _structured_facts(i.get("new_text", ""), i.get("source", "edit"))
            i["status"] = "confirmed" if action == "confirm" else "ignored"
            i["resolved_at"] = datetime.now().isoformat()
            found = i
            break
    if not found:
        raise ValueError("条目不存在")
    _save(client_id, items)
    return found


def merge_confirmed_into_kb(knowledge_md: str, client_id: str) -> str:
    """将已确认条目写入归属经历的固定模板字段。"""
    items = _load(client_id)
    confirmed = [i for i in items if i.get("status") == "confirmed"]
    if not confirmed:
        return knowledge_md
    merged = knowledge_md
    for item in confirmed[-20:]:
        title = (item.get("target_title") or "").strip()
        facts = item.get("facts") or _structured_facts(item.get("new_text", ""), item.get("source", "edit"))
        if not title or not facts:
            continue
        merged = _merge_facts_into_section(merged, title, facts)
        item["status"] = "merged"
        item["merged_at"] = datetime.now().isoformat()
    _save(client_id, items)
    return merged.rstrip() + "\n"


def _merge_facts_into_section(md: str, title: str, facts: list[dict]) -> str:
    lines = md.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == f"### {title}"), -1)
    if start < 0:
        section = [f"### {title}", *[f"- {field}：" for field in TEMPLATE_FIELDS]]
        insert_at = _project_section_insert_at(lines)
        lines[insert_at:insert_at] = ["", *section, ""]
        start = insert_at + 1

    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("### ") or lines[i].startswith("## ")), len(lines))
    section_lines = lines[start:end]
    for fact in facts:
        field = str(fact.get("field") or "").strip()
        value = str(fact.get("value") or "").strip()
        if field not in TEMPLATE_FIELDS or not value:
            continue
        prefix = f"- {field}："
        idx = next((i for i, line in enumerate(section_lines) if line.startswith(prefix)), -1)
        if idx >= 0:
            if value not in section_lines[idx]:
                sep = "；" if section_lines[idx].strip() != prefix else ""
                section_lines[idx] = f"{section_lines[idx]}{sep}{value}"
        else:
            section_lines.append(f"{prefix}{value}")
    lines[start:end] = section_lines
    return "\n".join(lines)


def _project_section_insert_at(lines: list[str]) -> int:
    idx = next((i for i, line in enumerate(lines) if line.strip() in ("## 实习 / 项目素材", "## 实习/项目素材")), -1)
    if idx < 0:
        lines.extend(["", "## 实习 / 项目素材"])
        return len(lines)
    next_h2 = next((i for i in range(idx + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return next_h2
