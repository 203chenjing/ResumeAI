from app.models.schemas import Session, Suggestion
from app.services.suggestion_apply import apply_suggestion_status


def _sess_with_suggestion() -> tuple[Session, Suggestion]:
    sess = Session(session_id="test")
    sess.current_resume_md = "原句内容。其他段落。"
    sug = Suggestion(
        id="s1",
        section="experience",
        type="wording",
        original_text="原句内容",
        suggested_text="优化后内容",
        reason="更量化",
    )
    sess.suggestions.append(sug)
    return sess, sug


def test_accept_replaces_text():
    sess, sug = _sess_with_suggestion()
    apply_suggestion_status(sess, sug, "accepted")
    assert "优化后内容" in sess.current_resume_md
    assert "原句内容" not in sess.current_resume_md


def test_reject_restores_text():
    sess, sug = _sess_with_suggestion()
    apply_suggestion_status(sess, sug, "accepted")
    apply_suggestion_status(sess, sug, "rejected")
    assert "原句内容" in sess.current_resume_md


def test_invalid_status_raises():
    sess, sug = _sess_with_suggestion()
    try:
        apply_suggestion_status(sess, sug, "invalid")  # type: ignore[arg-type]
        assert False, "should raise"
    except ValueError:
        pass
