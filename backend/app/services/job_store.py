"""SQLite job feed storage: incremental upsert, tombstones, JSON migration."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"
JSON_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "job_feed"
MAX_FEED_SIZE = 2000
STALE_MISS_THRESHOLD = 2
HIDDEN_JOB_DOMAINS = ("yingjiesheng.com",)

_migrated_clients: set[str] = set()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            client_id TEXT NOT NULL,
            id TEXT NOT NULL,
            company TEXT DEFAULT '',
            role TEXT DEFAULT '',
            source TEXT DEFAULT '',
            jd_text TEXT DEFAULT '',
            jd_url TEXT DEFAULT '',
            location TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            channel TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            city TEXT DEFAULT '',
            locations TEXT DEFAULT '[]',
            crawled_at TEXT DEFAULT '',
            published_at TEXT DEFAULT '',
            job_type TEXT DEFAULT '',
            source_site TEXT DEFAULT '',
            validation_status TEXT DEFAULT 'pending',
            validation_issues TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            last_seen_at TEXT DEFAULT '',
            miss_count INTEGER DEFAULT 0,
            ai_summary TEXT DEFAULT '',
            ai_tags TEXT DEFAULT '[]',
            referral_code TEXT DEFAULT '',
            legitimacy TEXT DEFAULT '',
            PRIMARY KEY (client_id, id)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_client_status ON jobs(client_id, status);
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(client_id, source);
        """
    )
    # 为旧库补列（CREATE TABLE IF NOT EXISTS 不会新增列）。
    existing_cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for col in ("referral_code", "legitimacy"):
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT DEFAULT ''")
    for col in ("graduation_cohort", "cohort_confidence"):
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT DEFAULT ''")
    for col in ("cross_verified", "verification_score", "verification_source_count"):
        if col not in existing_cols:
            conn.execute(
                f"ALTER TABLE jobs ADD COLUMN {col} {'INTEGER' if col != 'verification_score' else 'INTEGER'} DEFAULT 0"
            )
    if "source_attestations" not in existing_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN source_attestations TEXT DEFAULT '[]'")
    if "alternate_jd_urls" not in existing_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN alternate_jd_urls TEXT DEFAULT '[]'")
    conn.commit()


def _json_path(client_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in client_id)[:64] or "default"
    return JSON_DIR / f"{safe}.json"


def _migrate_json_if_needed(client_id: str) -> None:
    if client_id in _migrated_clients:
        return
    p = _json_path(client_id)
    if not p.exists():
        _migrated_clients.add(client_id)
        return
    try:
        legacy = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _migrated_clients.add(client_id)
        return
    if not isinstance(legacy, list) or not legacy:
        _migrated_clients.add(client_id)
        return
    conn = _conn()
    try:
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE client_id = ?", (client_id,)
        ).fetchone()
        if existing and existing["c"] > 0:
            _migrated_clients.add(client_id)
            return
        now = datetime.now().isoformat()
        for job in legacy:
            _upsert_one(conn, client_id, job, now=now)
        conn.commit()
        backup = p.with_suffix(".json.bak")
        if not backup.exists():
            p.rename(backup)
    finally:
        conn.close()
    _migrated_clients.add(client_id)


def _loads_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except Exception:
        return []


def _row_to_job(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "company": row["company"] or "",
        "role": row["role"] or "",
        "source": row["source"] or "",
        "jd_text": row["jd_text"] or "",
        "jd_url": row["jd_url"] or "",
        "location": row["location"] or "",
        "deadline": row["deadline"] or "",
        "channel": row["channel"] or "",
        "tags": _loads_list(row["tags"]),
        "city": row["city"] or "",
        "locations": _loads_list(row["locations"]),
        "crawled_at": row["crawled_at"] or "",
        "published_at": row["published_at"] or "",
        "job_type": row["job_type"] or "",
        "source_site": row["source_site"] or "",
        "validation_status": row["validation_status"] or "pending",
        "validation_issues": _loads_list(row["validation_issues"]),
        "status": row["status"] or "active",
        "last_seen_at": row["last_seen_at"] or "",
        "ai_summary": row["ai_summary"] or "",
        "ai_tags": _loads_list(row["ai_tags"]),
        "referral_code": (row["referral_code"] if "referral_code" in row.keys() else "") or "",
        "legitimacy": (row["legitimacy"] if "legitimacy" in row.keys() else "") or "",
        "graduation_cohort": (row["graduation_cohort"] if "graduation_cohort" in row.keys() else "") or "",
        "cohort_confidence": (row["cohort_confidence"] if "cohort_confidence" in row.keys() else "") or "",
        "cross_verified": bool(row["cross_verified"]) if "cross_verified" in row.keys() else False,
        "verification_score": int(row["verification_score"] or 0) if "verification_score" in row.keys() else 0,
        "verification_source_count": int(row["verification_source_count"] or 0) if "verification_source_count" in row.keys() else 0,
        "source_attestations": _loads_list(row["source_attestations"] if "source_attestations" in row.keys() else "[]"),
        "alternate_jd_urls": _loads_list(row["alternate_jd_urls"] if "alternate_jd_urls" in row.keys() else "[]"),
    }


def _is_hidden_job(job: dict) -> bool:
    url = job.get("jd_url") or ""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    if any(domain in host for domain in HIDDEN_JOB_DOMAINS):
        return True
    blob = " ".join(
        str(x or "")
        for x in (
            job.get("channel"),
            job.get("source_site"),
            *(job.get("tags") or []),
        )
    )
    return any(domain.replace(".com", "") in blob for domain in HIDDEN_JOB_DOMAINS)


def _upsert_one(conn: sqlite3.Connection, client_id: str, job: dict, *, now: str) -> None:
    conn.execute(
        """
        INSERT INTO jobs (
            client_id, id, company, role, source, jd_text, jd_url, location, deadline,
            channel, tags, city, locations, crawled_at, published_at, job_type, source_site,
            validation_status, validation_issues, status, last_seen_at, miss_count, ai_summary, ai_tags,
            referral_code, legitimacy, graduation_cohort, cohort_confidence,
            cross_verified, verification_score, verification_source_count,
            source_attestations, alternate_jd_urls
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(client_id, id) DO UPDATE SET
            company=excluded.company,
            role=excluded.role,
            source=excluded.source,
            jd_text=excluded.jd_text,
            jd_url=excluded.jd_url,
            location=excluded.location,
            deadline=excluded.deadline,
            channel=excluded.channel,
            tags=excluded.tags,
            city=excluded.city,
            locations=excluded.locations,
            crawled_at=excluded.crawled_at,
            published_at=excluded.published_at,
            job_type=excluded.job_type,
            source_site=excluded.source_site,
            validation_status=excluded.validation_status,
            validation_issues=excluded.validation_issues,
            status='active',
            last_seen_at=excluded.last_seen_at,
            miss_count=0,
            ai_summary=CASE WHEN excluded.ai_summary != '' THEN excluded.ai_summary ELSE jobs.ai_summary END,
            ai_tags=CASE WHEN excluded.ai_tags != '[]' THEN excluded.ai_tags ELSE jobs.ai_tags END,
            referral_code=CASE WHEN excluded.referral_code != '' THEN excluded.referral_code ELSE jobs.referral_code END,
            legitimacy=CASE WHEN excluded.legitimacy != '' THEN excluded.legitimacy ELSE jobs.legitimacy END,
            graduation_cohort=CASE WHEN excluded.graduation_cohort != '' THEN excluded.graduation_cohort ELSE jobs.graduation_cohort END,
            cohort_confidence=CASE WHEN excluded.cohort_confidence != '' THEN excluded.cohort_confidence ELSE jobs.cohort_confidence END,
            cross_verified=excluded.cross_verified,
            verification_score=excluded.verification_score,
            verification_source_count=excluded.verification_source_count,
            source_attestations=excluded.source_attestations,
            alternate_jd_urls=excluded.alternate_jd_urls
        """,
        (
            client_id,
            job.get("id", ""),
            job.get("company", ""),
            job.get("role", ""),
            job.get("source", ""),
            job.get("jd_text", ""),
            job.get("jd_url", ""),
            job.get("location", ""),
            job.get("deadline", ""),
            job.get("channel", ""),
            json.dumps(job.get("tags") or [], ensure_ascii=False),
            job.get("city", ""),
            json.dumps(job.get("locations") or [], ensure_ascii=False),
            job.get("crawled_at") or now,
            job.get("published_at", ""),
            job.get("job_type", ""),
            job.get("source_site", ""),
            job.get("validation_status", "pending"),
            json.dumps(job.get("validation_issues") or [], ensure_ascii=False),
            job.get("status", "active"),
            job.get("last_seen_at") or now,
            0,
            job.get("ai_summary", ""),
            json.dumps(job.get("ai_tags") or job.get("tags") or [], ensure_ascii=False),
            job.get("referral_code", ""),
            job.get("legitimacy", ""),
            job.get("graduation_cohort", ""),
            job.get("cohort_confidence", ""),
            1 if job.get("cross_verified") else 0,
            int(job.get("verification_score") or 0),
            int(job.get("verification_source_count") or 0),
            json.dumps(job.get("source_attestations") or [], ensure_ascii=False),
            json.dumps(job.get("alternate_jd_urls") or [], ensure_ascii=False),
        ),
    )


def list_jobs(
    client_id: str,
    source: str | None = None,
    *,
    job_type: str | None = None,
    work_city: str | None = None,
    graduation_cohort: str | None = None,
    include_unknown_cohort: bool = True,
    include_invalid: bool = False,
    include_weak: bool = True,
    include_expired: bool = False,
) -> list[dict]:
    _migrate_json_if_needed(client_id)
    conn = _conn()
    try:
        clauses = ["client_id = ?"]
        params: list = [client_id]
        if not include_expired:
            clauses.append("status = 'active'")
        if source:
            clauses.append("source = ?")
            params.append(source)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)
        if graduation_cohort:
            if include_unknown_cohort:
                clauses.append("(graduation_cohort = ? OR graduation_cohort = '' OR graduation_cohort IS NULL)")
                params.append(graduation_cohort)
            else:
                clauses.append("graduation_cohort = ?")
                params.append(graduation_cohort)
        sql = f"SELECT * FROM jobs WHERE {' AND '.join(clauses)}"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    jobs = [_row_to_job(r) for r in rows]
    jobs = [j for j in jobs if not _is_hidden_job(j)]
    if work_city:
        jobs = [
            j
            for j in jobs
            if work_city in (j.get("locations") or [])
            or work_city in (j.get("location") or "")
            or any(work_city in t for t in (j.get("tags") or []) if t.startswith("工作地:"))
        ]
    if not include_invalid:
        jobs = [j for j in jobs if j.get("validation_status") != "invalid"]
    if not include_weak:
        jobs = [j for j in jobs if j.get("validation_status") != "weak"]
    jobs.sort(
        key=lambda j: j.get("published_at") or j.get("crawled_at") or "",
        reverse=True,
    )
    return jobs


def save_all(client_id: str, jobs: list[dict]) -> None:
    _migrate_json_if_needed(client_id)
    now = datetime.now().isoformat()
    conn = _conn()
    try:
        conn.execute("DELETE FROM jobs WHERE client_id = ?", (client_id,))
        for job in jobs[:MAX_FEED_SIZE]:
            _upsert_one(conn, client_id, job, now=now)
        conn.commit()
    finally:
        conn.close()


def upsert_jobs(client_id: str, jobs: list[dict]) -> None:
    _migrate_json_if_needed(client_id)
    now = datetime.now().isoformat()
    conn = _conn()
    try:
        for job in jobs:
            if not job.get("id"):
                continue
            job = {**job, "last_seen_at": now, "status": "active", "miss_count": 0}
            _upsert_one(conn, client_id, job, now=now)
        conn.commit()
        _trim_client(conn, client_id)
        conn.commit()
    finally:
        conn.close()


def _trim_client(conn: sqlite3.Connection, client_id: str) -> None:
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM jobs WHERE client_id = ? AND status = 'active'",
        (client_id,),
    ).fetchone()["c"]
    if count <= MAX_FEED_SIZE:
        return
    excess = count - MAX_FEED_SIZE
    stale_ids = conn.execute(
        """
        SELECT id FROM jobs
        WHERE client_id = ? AND status = 'active'
        ORDER BY COALESCE(published_at, crawled_at, last_seen_at) ASC
        LIMIT ?
        """,
        (client_id, excess),
    ).fetchall()
    for row in stale_ids:
        conn.execute(
            "UPDATE jobs SET status = 'expired' WHERE client_id = ? AND id = ?",
            (client_id, row["id"]),
        )


def mark_unseen_stale(client_id: str, seen_ids: set[str], *, sources: set[str] | None = None) -> int:
    """连续未出现的岗位递增 miss_count，超过阈值标记 expired。"""
    _migrate_json_if_needed(client_id)
    conn = _conn()
    expired = 0
    try:
        clauses = ["client_id = ?", "status = 'active'"]
        params: list = [client_id]
        if sources:
            placeholders = ",".join("?" * len(sources))
            clauses.append(f"source IN ({placeholders})")
            params.extend(list(sources))
        rows = conn.execute(
            f"SELECT id FROM jobs WHERE {' AND '.join(clauses)}",
            params,
        ).fetchall()
        for row in rows:
            jid = row["id"]
            if jid in seen_ids:
                continue
            conn.execute(
                """
                UPDATE jobs SET miss_count = miss_count + 1,
                status = CASE WHEN miss_count + 1 >= ? THEN 'expired' ELSE status END
                WHERE client_id = ? AND id = ?
                """,
                (STALE_MISS_THRESHOLD, client_id, jid),
            )
            if conn.execute(
                "SELECT status FROM jobs WHERE client_id = ? AND id = ?",
                (client_id, jid),
            ).fetchone()["status"] == "expired":
                expired += 1
        conn.commit()
    finally:
        conn.close()
    return expired


def feed_meta(client_id: str) -> dict:
    jobs = list_jobs(client_id, include_weak=True)
    types: dict[str, int] = {}
    sources: dict[str, int] = {}
    cities: dict[str, int] = {}
    cohorts: dict[str, int] = {}
    cross_verified_count = 0
    for j in jobs:
        jt = j.get("job_type") or "校招"
        types[jt] = types.get(jt, 0) + 1
        src = j.get("source") or "unknown"
        sources[src] = sources.get(src, 0) + 1
        cohort = j.get("graduation_cohort") or "未知"
        cohorts[cohort] = cohorts.get(cohort, 0) + 1
        if j.get("cross_verified"):
            cross_verified_count += 1
        for loc in j.get("locations") or []:
            cities[loc] = cities.get(loc, 0) + 1
    crawled = [j.get("crawled_at") for j in jobs if j.get("crawled_at")]
    return {
        "total": len(jobs),
        "job_types": types,
        "sources": sources,
        "work_cities": cities,
        "graduation_cohorts": cohorts,
        "cross_verified_count": cross_verified_count,
        "last_crawled_at": max(crawled) if crawled else "",
        "storage": "sqlite",
    }


def update_job_fields(client_id: str, job_id: str, fields: dict) -> None:
    if not fields:
        return
    allowed = {
        "company", "role", "jd_text", "tags", "locations", "location", "deadline",
        "job_type", "validation_status", "validation_issues", "ai_summary", "ai_tags",
        "graduation_cohort", "cohort_confidence",
        "cross_verified", "verification_score", "verification_source_count",
        "source_attestations", "alternate_jd_urls",
    }
    sets = []
    params: list = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("tags", "locations", "validation_issues", "ai_tags", "source_attestations", "alternate_jd_urls") and isinstance(v, list):
            v = json.dumps(v, ensure_ascii=False)
        if k == "cross_verified":
            v = 1 if v else 0
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return
    params.extend([client_id, job_id])
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE jobs SET {', '.join(sets)} WHERE client_id = ? AND id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()
