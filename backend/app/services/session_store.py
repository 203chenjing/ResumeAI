"""会话管理：SQLite 持久化 + 超时清理。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

from app.config import settings
from app.models.schemas import Session

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sessions.db"


class SessionStore:
    def __init__(self):
        self._lock = Lock()
        self._sessions: dict[str, Session] = {}
        self._init_db()

    def _init_db(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    last_activity TEXT NOT NULL
                )
                """
            )

    def _persist(self, session_id: str, sess: Session) -> None:
        payload = sess.model_dump(mode="json")
        last = sess.last_activity.isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, data, last_activity)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    data = excluded.data,
                    last_activity = excluded.last_activity
                """,
                (session_id, json.dumps(payload, ensure_ascii=False), last),
            )

    def _load_from_db(self, session_id: str) -> Session | None:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT data FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return Session.model_validate(json.loads(row[0]))

    def create(self) -> Session:
        sid = uuid.uuid4().hex
        sess = Session(session_id=sid)
        with self._lock:
            self._sessions[sid] = sess
            self._persist(sid, sess)
        return sess

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is None:
                sess = self._load_from_db(session_id)
                if sess is None:
                    return None
                self._sessions[session_id] = sess
            sess.last_activity = datetime.now()
            self._persist(session_id, sess)
            return sess

    def list_recent(self, limit: int = 10) -> list[dict]:
        """返回最近会话存档摘要，供首页恢复工作区。"""
        safe_limit = max(1, min(limit, 50))
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT session_id, data, last_activity
                FROM sessions
                ORDER BY last_activity DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        out: list[dict] = []
        for sid, raw, last_activity in rows:
            try:
                sess = Session.model_validate(json.loads(raw))
            except Exception:
                continue
            company = sess.jd_analysis.company if sess.jd_analysis else ""
            role = sess.jd_analysis.role if sess.jd_analysis else ""
            pending = len([s for s in sess.suggestions if s.status in ("pending", "adjusted")])
            title_parts = [p for p in (company, role) if p]
            title = " · ".join(title_parts) or _fallback_session_title(sess)
            out.append(
                {
                    "session_id": sid,
                    "title": title,
                    "company": company,
                    "role": role,
                    "status": sess.status,
                    "finalize_status": sess.finalize_status,
                    "pending_suggestions": pending,
                    "suggestions_total": len(sess.suggestions),
                    "has_finalized": bool(sess.finalized_resume_md),
                    "updated_at": last_activity,
                    "created_at": sess.created_at.isoformat(),
                }
            )
        return out

    def update(self, session: Session):
        session.last_activity = datetime.now()
        with self._lock:
            self._sessions[session.session_id] = session
            self._persist(session.session_id, session)

    def cleanup(self):
        """清理过期会话（内存 + SQLite）。"""
        timeout = timedelta(minutes=settings.session_timeout_minutes)
        now = datetime.now()
        with self._lock:
            expired: list[str] = []
            for sid, s in list(self._sessions.items()):
                if now - s.last_activity > timeout:
                    expired.append(sid)
            for sid in expired:
                del self._sessions[sid]

            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT session_id, last_activity FROM sessions"
                ).fetchall()
                for sid, last_str in rows:
                    try:
                        last = datetime.fromisoformat(last_str)
                    except ValueError:
                        expired.append(sid)
                        continue
                    if now - last > timeout:
                        expired.append(sid)
                for sid in set(expired):
                    conn.execute(
                        "DELETE FROM sessions WHERE session_id = ?",
                        (sid,),
                    )


def _fallback_session_title(sess: Session) -> str:
    if sess.parsed_resume and sess.parsed_resume.header.name:
        return f"{sess.parsed_resume.header.name} 的简历工作区"
    if sess.current_resume_md:
        return "未命名简历工作区"
    return "空白工作区"


store = SessionStore()
