# story_bank 召回改造方案

## 目标

从 `简历数据库.md`（L1 STAR 层）按 JD / archetype **召回 top-K 经历条目**，供：

- `build_resume_from_knowledge` 缩小 LLM 上下文
- 秋招 `batch_run` 批量成稿前的 bullet 选择
- `interview_prep` 面试故事匹配

## 数据流

```
简历数据库.md
    ↓ parse_stories_from_kb()
list[Story]  （L1 单元，含 meta/tags/archetypes）
    ↓ recall_stories(jd_text, archetype=…)
top-K Story + score_breakdown
    ↓ format_recall_context()
Markdown 片段 → 注入 resume_from_knowledge prompt
```

## Story 字段（L1 单元）

| 字段 | 来源 | 召回用途 |
|------|------|----------|
| `id` | `story-id` 或自动生成 | 溯源、L2 映射引用 |
| `title` | `#### STAR N：` 标题 | 展示 |
| `employer` / `project` | 上级 `##` 标题 + meta | 过滤、分组 |
| `priority` | P0/P1/P2 | P0 +0.12 加权 |
| `tags` | `#tag` + meta tags | token 命中 |
| `fit_archetypes` | meta archetypes | archetype 命中 +0.15 |
| `evidence_ids` | meta evidence | 审计，不参与打分 |
| `resume_ready` | meta resume-ready | 批量 T1 可过滤 |
| STAR 五段 | `- **背景**` 等 | 语义相似度主体 |

## 解析规则

1. **L1 边界**：`## …｜…` 雇主块内，`#### STAR` 开头为一条 Story。
2. **meta 行**：紧挨标题的 `> story-id: … · level: L1 · …` blockquote；缺省时从标题生成 `s{N}`。
3. **L0 不召回**：无 `#### STAR` 的 L0 线索仅作证据，不进入 `list[Story]`。
4. **L2 不召回**：`## L2` 区块跳过（策略层单独读映射表，未来可拆 `parse_l2_strategy()`）。
5. **向后兼容**：旧库无 meta 行时，仍解析 `###` 下 STAR 五段 + `#tags`。

## 召回算法（无向量库阶段）

综合分 = 加权求和，**不用硬编码中文关键词表**：

| 信号 | 权重 | 说明 |
|------|------|------|
| token_overlap | 0.40 | JD/query 与 story 全文字符 token 交集（与 edit_catalog 同 `_TOKEN`） |
| sequence_similarity | 0.25 | `SequenceMatcher` 整段相似度 |
| tag_overlap | 0.15 | JD token 与 tags/archetypes 命中 |
| archetype_boost | 0.12 | `infer_role_bucket(jd)` 或传入 archetype 与 `fit_archetypes` 模糊匹配 |
| priority_boost | 0.08 | P0=1.0, P1=0.5, P2=0.2 × 权重 |

- `min_score` 默认 `0.12`；无命中时 fallback 返回 P0 故事或前 `top_k` 条。
- 可选 `employer=` 过滤、`resume_ready_only=True` 用于 T1 自动批。

## API  surface

```python
from app.services.story_bank import (
    parse_stories_from_kb,
    recall_stories,
    format_recall_context,
)

stories = parse_stories_from_kb(knowledge_md)
hits = recall_stories(
    stories,
    jd_text,
    archetype="软件产品经理",  # 可选，来自 role_lens / jd_analysis
    top_k=8,
    min_score=0.12,
)
ctx = format_recall_context(hits)  # 注入 prompt
```

## 与 build_resume_from_knowledge 集成（下一步）

在 `build_resume_from_knowledge_prompt` 中增加可选块：

```markdown
## 本次 JD 召回的 L1 经历（优先使用，勿编造库外事实）

{format_recall_context(hits)}
```

完整 KB 仍附后作为 fallback，但 token 优先消耗召回块。

## 与 L2 映射联动（下一步）

`parse_l2_mapping(kb_md, archetype)` 读取 `### L2-JD 映射笔记` 下优先 `story-id` 列表，在 `recall_stories` 结果上 **重排序**（映射命中 +0.2），而非写死 JD 关键词。

## 测试

- `test_parse_stories_l1_meta`：meta 行解析 employer/archetypes
- `test_recall_by_jd_semantic`：JD 含「总结卡」召回 EPIC 故事（样本 KB）
- `test_recall_archetype_boost`：同 JD 不同 archetype 排序变化
- `test_backward_compat`：无 meta 的旧 SAMPLE_KB 仍通过

## 演进路线

| 阶段 | 能力 |
|------|------|
| **现在** | 结构化解析 + 语义/token 召回 |
| Phase 2 | L2 story-id 优先重排 |
| Phase 3 | 可选 embedding（Qdrant/pgvector） |
| Phase 4 | 批量 run 写回「上次用于：美团商分」到 meta |
