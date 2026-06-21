from datetime import datetime, timedelta

from app.config import settings
from app.models.schemas import Session
from app.services.session_store import SessionStore


def test_create_and_get_session():
    store = SessionStore()
    sess = store.create()
    assert sess.session_id
    got = store.get(sess.session_id)
    assert got is not None
    assert got.session_id == sess.session_id


def test_cleanup_expired_sessions():
    store = SessionStore()
    sess = store.create()
    expired_time = datetime.now() - timedelta(
        minutes=settings.session_timeout_minutes + 1
    )
    # update() 会刷新 last_activity，直接写入存储层
    with store._lock:
        store._sessions[sess.session_id].last_activity = expired_time
        store._persist(sess.session_id, store._sessions[sess.session_id])
    store.cleanup()
    assert store.get(sess.session_id) is None
