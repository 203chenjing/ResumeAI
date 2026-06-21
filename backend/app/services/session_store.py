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


store = SessionStore()
