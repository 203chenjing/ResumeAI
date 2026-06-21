"""Pytest 公共 fixture。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# backend/ 作为导入根
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "golden"


@pytest.fixture
def tmp_user_memory(monkeypatch, tmp_path):
    """将 user_memory 指向临时目录，避免污染开发数据。"""
    mem_dir = tmp_path / "user_memory"
    mem_dir.mkdir()
    import app.services.user_memory as um

    monkeypatch.setattr(um, "DATA_DIR", mem_dir)
    return mem_dir
