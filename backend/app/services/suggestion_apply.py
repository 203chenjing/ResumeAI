"""建议状态变更并同步简历工作稿。"""
from app.models.schemas import Suggestion
from app.routers.finalize import mark_finalize_stale
from app.services.resume_density import assess_density
from app.services.session_sync import refresh_match


def apply_suggestion_status(sess, target: Suggestion, status: str) -> None:
    if status not in ("pending", "accepted", "rejected", "adjusted"):
        raise ValueError("非法状态")

    target.status = status

    if status == "accepted" and target.original_text and target.suggested_text:
        if target.original_text in sess.current_resume_md:
            sess.current_resume_md = sess.current_resume_md.replace(
                target.original_text, target.suggested_text, 1
            )
    elif status in ("pending", "rejected"):
        if target.suggested_text in sess.current_resume_md and target.original_text:
            sess.current_resume_md = sess.current_resume_md.replace(
                target.suggested_text, target.original_text, 1
            )

    mark_finalize_stale(sess)


async def apply_status_update(sess, suggestion_id: str, status: str) -> dict:
    target = next((s for s in sess.suggestions if s.id == suggestion_id), None)
    if not target:
        raise ValueError("建议不存在")
    apply_suggestion_status(sess, target, status)
    match = await refresh_match(sess)
    density = assess_density(sess.current_resume_md)
    return {
        "suggestion": target.model_dump(),
        "match": match.model_dump() if match else None,
        "density": density,
    }
