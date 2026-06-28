"""job_store SQLite 存储测试。"""
import json
from pathlib import Path

import pytest

from app.services import job_store


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    json_dir = tmp_path / "job_feed"
    monkeypatch.setattr(job_store, "DB_PATH", db)
    monkeypatch.setattr(job_store, "JSON_DIR", json_dir)
    job_store._migrated_clients.clear()


def test_upsert_and_list():
    client = "test-client"
    jobs = [
        {
            "id": "j1",
            "company": "测试公司",
            "role": "后端开发",
            "source": "job_aggregator",
            "jd_text": "招聘后端",
            "validation_status": "ok",
            "tags": ["校招"],
            "locations": ["北京"],
        }
    ]
    job_store.save_all(client, jobs)
    loaded = job_store.list_jobs(client)
    assert len(loaded) == 1
    assert loaded[0]["company"] == "测试公司"


def test_json_migration(tmp_path, monkeypatch):
    client = "migrate-me"
    json_dir = tmp_path / "job_feed"
    json_dir.mkdir()
    legacy = [{"id": "old1", "company": "旧数据", "role": "实习", "source": "university_html", "jd_text": "x"}]
    (json_dir / "migrate-me.json").write_text(json.dumps(legacy), encoding="utf-8")

    loaded = job_store.list_jobs(client)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "old1"
    assert not (json_dir / "migrate-me.json").exists()
    assert (json_dir / "migrate-me.json.bak").exists()
