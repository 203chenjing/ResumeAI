"""L5 摘要记忆：会话级压缩笔记，供长对话 compaction。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.schemas import Session

logger = logging.getLogger(__name__)

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "session_memory"


def _summary_path(session_id: str) -> Path:
    return DATA_ROOT / session_id / "summary.md"


def read_summary(session_id: str) -> str:
    path = _summary_path(session_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_summary(session_id: str, content: str) -> None:
    path = _summary_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"<!-- updated: {datetime.now(timezone.utc).isoformat()} -->\n\n"
    path.write_text(header + content.strip() + "\n", encoding="utf-8")


def should_summarize(sess: Session) -> bool:
    threshold = getattr(settings, "memory_summary_threshold", 12)
    return len(sess.chat_history) >= threshold


def build_rolling_summary(sess: Session) -> str:
    """规则型滚动摘要（无 LLM 依赖）；后续可换后台子代理。"""
    lines = [
        f"# 会话摘要 · {sess.session_id[:8]}",
        "",
        f"- 状态: {sess.status}",
        f"- 定稿: {sess.finalize_status}",
    ]
    if sess.jd_analysis:
        lines.append(f"- 目标岗位: {sess.jd_analysis.role}")
    if sess.match_result:
        lines.append(f"- 匹配分: {sess.match_result.overall_score}")
    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
    lines.append(f"- 待处理建议: {len(pending)} / {len(sess.suggestions)}")
    lines.append("")
    lines.append("## 近期对话要点")
    for m in sess.chat_history[-6:]:
        role = "用户" if m.role == "user" else "助手"
        text = m.content.replace("\n", " ").strip()[:120]
        lines.append(f"- **{role}**: {text}")
    agent_prefs = getattr(sess, "agent_prefs", None) or {}
    if agent_prefs:
        lines.extend(["", "## Agent 备注", f"```json\n{agent_prefs}\n```"])
    return "\n".join(lines)


def maybe_update_summary(sess: Session) -> str | None:
    if not should_summarize(sess):
        return None
    summary = build_rolling_summary(sess)
    write_summary(sess.session_id, summary)
    return summary


def summary_context(session_id: str) -> str:
    body = read_summary(session_id).strip()
    if not body:
        return ""
    return f"==== L5 会话摘要 ====\n{body[:2000]}\n==== L5 结束 ===="
