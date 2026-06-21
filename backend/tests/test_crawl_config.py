"""crawl_sources.yml 加载测试。"""
from pathlib import Path

from app.crawlers.crawl_config import get_provider_config, load_crawl_config, reload_crawl_config


def test_load_crawl_config_has_sources():
    cfg = reload_crawl_config()
    uni = get_provider_config("university_html")
    assert uni.get("enabled") is True
    sources = uni.get("sources") or []
    assert len(sources) >= 3
    assert any(s.get("id") == "tsinghua-xxfb" for s in sources)


def test_config_file_exists():
    path = Path(__file__).resolve().parents[1] / "crawl_sources.yml"
    assert path.exists()
    cfg = load_crawl_config()
    assert "compliance" in cfg
    assert cfg["compliance"].get("rate_limit_rps", 0) > 0
