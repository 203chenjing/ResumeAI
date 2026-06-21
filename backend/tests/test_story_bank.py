"""故事库解析测试。"""
from app.services.story_bank import parse_stories_from_kb, search_stories


SAMPLE_KB = """
## 实习素材

### 某厂 · 后端实习
- **背景**：电商大促期间
- **任务**：优化订单接口
- **行动**：引入 Redis 缓存与异步队列
- **结果**：P99 延迟降低 40%
"""


def test_parse_stories():
    stories = parse_stories_from_kb(SAMPLE_KB)
    assert len(stories) >= 1
    assert "某厂" in stories[0].title or "后端" in stories[0].title


def test_search_stories():
    stories = parse_stories_from_kb(SAMPLE_KB)
    hits = search_stories(stories, "Redis 缓存 后端", top_k=3)
    assert len(hits) >= 1
