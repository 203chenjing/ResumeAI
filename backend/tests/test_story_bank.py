"""故事库解析与召回测试。"""
from app.services.story_bank import (
    format_recall_context,
    parse_stories_from_kb,
    recall_stories,
    search_stories,
)

SAMPLE_KB = """
## 实习素材

### 某厂 · 后端实习
- **背景**：电商大促期间
- **任务**：优化订单接口
- **行动**：引入 Redis 缓存与异步队列
- **结果**：P99 延迟降低 40%
"""

L1_KB = """
## 携程计算机技术（上海）有限公司｜AI 搜索产品实习生

#### STAR 1：AI 总结卡触发规则

> story-id: `ct-epic-01` · level: L1 · priority: P0 · archetypes: AI产品, 软件产品经理 · tags: #总结卡 #Prompt · evidence: ev-01 · resume-ready: yes

- **背景**：泛意图 query 下用户看不懂推荐逻辑
- **任务**：定义 AI 总结卡何时露出、首位还是腰部
- **行动**：输出触发矩阵与 Prompt PRD
- **结果**：腰部插入场景跳出率降低 2pp

#### STAR 2：Agent 工作流搭建

> story-id: `ct-agent-01` · level: L1 · priority: P1 · archetypes: AI产品 · tags: #Dify #Agent · resume-ready: no

- **背景**：Case 排障入口分散
- **任务**：设计 7 步 Agent 链路
- **行动**：Dify 编排 Tool 调用与证据链
- **结果**：可演示原型就绪
"""

JD_EPIC = """
数据产品经理实习生：负责搜索场景 AI 功能，需要 Prompt 设计、用户画像、
A/B 实验与结果页总结卡体验优化。
"""

JD_AGENT = """
AI Agent 产品：Dify 工作流、Tool 封装、Case 排障、LLM 规划。
"""


def test_parse_stories_legacy():
    stories = parse_stories_from_kb(SAMPLE_KB)
    assert len(stories) >= 1
    assert "某厂" in stories[0].title or "后端" in stories[0].title


def test_search_stories_legacy():
    stories = parse_stories_from_kb(SAMPLE_KB)
    hits = search_stories(stories, "Redis 缓存 后端", top_k=3)
    assert len(hits) >= 1


def test_parse_l1_meta():
    stories = parse_stories_from_kb(L1_KB)
    assert len(stories) == 2
    epic = next(s for s in stories if s.id == "ct-epic-01")
    assert epic.priority == "P0"
    assert "AI产品" in epic.fit_archetypes
    assert epic.resume_ready is True
    assert "携程" in epic.employer


def test_recall_epic_over_agent():
    stories = parse_stories_from_kb(L1_KB)
    hits = recall_stories(stories, JD_EPIC, archetype="软件产品经理", top_k=2)
    assert hits[0].id == "ct-epic-01"
    assert hits[0].score > 0


def test_recall_agent_jd():
    stories = parse_stories_from_kb(L1_KB)
    hits = recall_stories(stories, JD_AGENT, top_k=2)
    assert any(s.id == "ct-agent-01" for s in hits)


def test_format_recall_context():
    stories = parse_stories_from_kb(L1_KB)
    hits = recall_stories(stories, JD_EPIC, top_k=1)
    ctx = format_recall_context(hits)
    assert "ct-epic-01" in ctx
    assert "背景" in ctx
