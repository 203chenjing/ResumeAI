"""会话侧状态同步：建议 upsert、匹配度刷新、会话快照。"""
import logging

from app.models.schemas import Suggestion
from app.services.match_analyzer import analyze_match
from app.services.resume_density import assess_density

logger = logging.getLogger(__name__)


def upsert_suggestions(sess, raw_list: list[dict]) -> list[Suggestion]:
    """按 id 插入或更新建议，返回本次处理的建议列表。"""
    updated: list[Suggestion] = []
    for raw in raw_list:
        try:
            raw.setdefault("status", "pending")
            raw.setdefault("line_range", [0, 0])
            raw.setdefault("jd_match_points", [])
            sug = Suggestion(**raw)
        except Exception as e:
            logger.warning("Skip invalid suggestion: %s, raw=%s", e, raw)
            continue

        replaced = False
        for i, existing in enumerate(sess.suggestions):
            if existing.id == sug.id:
                sess.suggestions[i] = sug
                replaced = True
                break
        if not replaced:
            sess.suggestions.append(sug)
        updated.append(sug)
    return updated


async def refresh_match(sess):
    """根据当前工作稿重新计算匹配度。"""
    if not sess.jd_analysis or not sess.current_resume_md:
        return sess.match_result
    sess.match_result = await analyze_match(sess.current_resume_md, sess.jd_analysis)
    return sess.match_result


def build_session_payload(sess) -> dict:
    """构建可推送给前端的会话快照（done 事件用）。"""
    return {
        "session": {
            "status": sess.status,
            "current_resume_md": sess.current_resume_md,
            "finalized_resume_md": sess.finalized_resume_md,
            "finalize_status": sess.finalize_status,
            "suggestions": [s.model_dump() for s in sess.suggestions],
            "match": sess.match_result.model_dump() if sess.match_result else None,
            "jd_analysis": sess.jd_analysis.model_dump() if sess.jd_analysis else None,
            "density": assess_density(sess.current_resume_md),
            "agent_prefs": getattr(sess, "agent_prefs", None) or {},
        },
    }


def build_ui_patch_for_suggestions(new_sugs: list[dict]) -> dict:
    """新建议写入后，通知前端切换筛选并高亮卡片。"""
    ids = [s.get("id") for s in new_sugs if s.get("id")]
    if not ids:
        return {}
    return {
        "filter": "pending",
        "highlight_ids": ids,
        "focus_panel": "suggestions",
    }


def build_ui_patch_for_pending(sess, *, user_message: str = "", reply: str = "") -> dict:
    """用户追问或 get_state 时，引导左侧展示待处理建议。"""
    pending = [s for s in sess.suggestions if s.status in ("pending", "adjusted")]
    if not pending:
        return {}
    msg = user_message or ""
    focus_keys = ("在哪", "没看到", "看不到", "哪里", "左侧", "修改建议", "建议在哪")
    if any(k in msg for k in focus_keys) or "待处理" in (reply or ""):
        return {
            "filter": "pending",
            "highlight_ids": [s.id for s in pending],
            "focus_panel": "suggestions",
        }
    return {}
