# ResumeAI 六层记忆分层架构

> 参考来源：晨 TR058485 · Claude Code 记忆子系统（[luyao618/Claude-Code-Source-Study](https://github.com/luyao618/Claude-Code-Source-Study) Ch.31）  
> 高星对标见 [REFERENCE_REPOS.md](./REFERENCE_REPOS.md#记忆层对标)

## 一、整体架构（核心框架）

```
┌─────────────────────────────────────────────────────────────────┐
│  L1 指令记忆   CLAUDE.md / AGENTS.md / skills/*.md              │
├─────────────────────────────────────────────────────────────────┤
│  L2 短期记忆   完整对话历史 → 零压缩（Session.chat_history）     │
├─────────────────────────────────────────────────────────────────┤
│  L3 工作记忆   进度 / 偏移 / 投机（Session.working_memory）      │
├─────────────────────────────────────────────────────────────────┤
│  L4 长期记忆   memdir 知识库 · MEMORY.md 全局索引 · 自动维护     │
├─────────────────────────────────────────────────────────────────┤
│  L5 摘要记忆   Session Memory → 后台压缩会话笔记                 │
├─────────────────────────────────────────────────────────────────┤
│  L6 休眠重塑   AutoDream → 离线整合 · 去重 · 更新索引            │
└─────────────────────────────────────────────────────────────────┘
```

| 层级 | 名称 | 生命周期 | 存储位置 | 核心职责 |
|------|------|----------|----------|----------|
| L1 | 指令记忆 | 永久 | `CLAUDE.md`、`skills/` | 规则级静态指令，人写、版本控制 |
| L2 | 短期记忆 | 会话级 | `Session.chat_history`（SQLite） | 完整对话，**零压缩**注入 Planner |
| L3 | 工作记忆 | 任务级 | `Session.working_memory` | 当前任务进度、步骤偏移、投机缓存 |
| L4 | 长期记忆 | 跨会话持久 | `data/memdir/{client_id}/` | 分层知识库 + `MEMORY.md` 索引 |
| L5 | 摘要记忆 | 压缩级 | `data/session_memory/{session_id}/summary.md` | 会话笔记，供长对话 compaction |
| L6 | 休眠重塑 | 离线级 | 写回 memdir | 清理、合并、去矛盾、刷新 `MEMORY.md` |

---

## 二、各层详解与 ResumeAI 映射

### L1 指令记忆【规则级别】

**CLAUDE.md 文件族**：项目根 `CLAUDE.md`、各 `skills/*/SKILL.md`、可选 `.cursor/rules/`。

- 加载顺序：Managed → User → Project → Local（后加载优先级更高）
- 不随用户对话自动改写；变更走 Git / 人工评审
- ResumeAI 约定：不写死改稿流水线，规则写在 `CLAUDE.md` + `skills/resume-agent/SKILL.md`

### L2 短期记忆【会话级别】

**完整对话历史 → 零压缩**

- 实现：`backend/app/models/schemas.py` → `Session.chat_history`
- 持久化：`session_store.py`（SQLite `data/sessions.db`）
- Planner 默认取最近 8 条；**长会话**由 L5 摘要补充，但不删除原始 history
- 对标：Claude Code `sessionStorage.ts` JSONL 全量 transcript

### L3 工作记忆【任务级别】

**进度 / 偏移 / 投机**

```json
{
  "goal": "针对字节后端岗完成匹配与建议",
  "current_step": "generate_suggestions",
  "completed_steps": ["analyze_jd", "analyze_match"],
  "speculation": { "next_action": "review_suggestions", "confidence": 0.7 },
  "checkpoint": { "match_score": 72, "pending_count": 5 }
}
```

- 实现：`working_memory.py` + `Session.working_memory`
- 每轮 Agent 结束后更新；供 Planner 避免重复步骤
- 对标：Claude Code Agent Memory 的任务级 checkpoint

### L4 长期记忆【持久级别】

**memdir 知识库 — 最核心**

```
data/memdir/{client_id}/
├── MEMORY.md              # 全局索引（≤200 行 / 25KB）
├── topics/
│   ├── knowledge-base.md  # 经历素材（与 API knowledge_base_md 同步）
│   ├── preferences.md     # 写作偏好
│   ├── job-targets.md     # 目标岗位 / 行业
│   └── star-stories.md    # STAR 案例库
├── logs/                  # 增量记忆日志（可选）
├── .dream-state.json      # AutoDream 状态
└── .consolidate-lock      # 整合锁
```

- `MEMORY.md` 仅为**指针索引**，每行指向一个 topic 文件
- 会话加载时注入索引 + 按需召回相关 topic（见 `memdir.py`）
- 与现有 `user_memory.py` JSON 存储**双写兼容**：API 不变，memdir 为结构化演进方向

### L5 摘要记忆【压缩级别】

**Session Memory — 压缩机制**

- 路径：`data/session_memory/{session_id}/summary.md`
- 触发：对话 ≥12 条或字符超阈值时，后台子逻辑滚动更新摘要
- 用途：Planner 上下文用「摘要 + 最近 N 条」替代全量 history
- 对标：Claude Code `sessionMemory.ts` + `summary.md`

### L6 休眠重塑【离线级别】

**AutoDream — 整合流程**

**双闸门触发（AND）：**

| 闸门 | 条件 | 默认 |
|------|------|------|
| 时间 | 距上次成功整合 | ≥ 24h |
| 会话 | 累计新会话数 | ≥ 5 |

**整合动作：**

1. 扫描 memdir 与 `session_memory/` 归档
2. 合并重复 topic、删除过时指针
3. 解决矛盾（以最新用户确认为准）
4. 压缩 `MEMORY.md` 超长行 → 移入 topic 正文
5. 更新 `.dream-state.json`

- 实现：`auto_dream.py`；可 `POST /api/memory/consolidate` 手动触发
- 对标：Claude Code `autoDream.ts` + `/dream` Skill

---

## 三、数据流

```
用户消息
   │
   ├─→ L2 chat_history（追加，零压缩）
   │
   ├─→ L3 working_memory（更新步骤）
   │
   ├─→ L4 memdir（偏好/知识库变更时写入）
   │
   └─→ Planner 上下文拼装
          ├─ L1 CLAUDE.md（系统侧）
          ├─ L4 MEMORY.md + 相关 topics
          ├─ L5 session summary（若有）
          ├─ L2 最近 N 条对话
          └─ L3 working_memory 快照

会话结束 / 定时
   │
   ├─→ L5 更新 summary.md
   │
   └─→ L6 AutoDream（24h + 5 会话）
          └─→ 刷新 L4 MEMORY.md + topics
```

---

## 四、GitHub 高星对标

| 项目 | Stars | 记忆相关能力 | 与 ResumeAI 关系 |
|------|-------|--------------|------------------|
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | ~60k | 用户/会话/Agent 三层记忆、自编辑去重、向量+图混合检索 | L4 长期记忆可选后端；生产级 RAG 记忆层 |
| [luyao618/Claude-Code-Source-Study](https://github.com/luyao618/Claude-Code-Source-Study) | ~2k | 七层记忆架构源码研读、AutoDream、memdir | **本架构直接参考** |
| [HFurther/claude-code-stable](https://github.com/HFurther/claude-code-stable) | — | AutoDream 文档、consolidation 四阶段 | L6 触发与整合流程 |
| [getzep/zep](https://github.com/getzep/zep) | ~20k | 时序知识图、事实有效期窗口 | 若需「偏好随时间演变」可评估 |
| [letta-ai/letta](https://github.com/letta-ai/letta) | ~20k | 分层 core/archival/recall 记忆 | 长运行 Agent 参考 |
| [santifer/career-ops](https://github.com/santifer/career-ops) | ~55k | story-bank、DATA_CONTRACT 用户/系统分层 | 求职域长期记忆模式 |

### 选型建议

- **默认路径**：文件型 memdir（L4）+ SQLite 会话（L2/L3），零额外依赖，与现有 `user_memory` API 兼容
- **规模化**：接入 Mem0 托管层，保留 `MEMORY.md` 作人工可读索引
- **时序推理**：拒信模式、偏好演变等场景可评估 Zep Graphiti

---

## 五、API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/user-memory/{client_id}` | 长期记忆（兼容旧版 JSON） |
| PUT | `/api/user-memory` | 保存长期记忆（双写 memdir） |
| GET | `/api/memory/index/{client_id}` | 读取 `MEMORY.md` 索引 |
| GET | `/api/memory/topics/{client_id}` | 列出 topic 文件 |
| GET | `/api/memory/session/{session_id}` | 会话摘要（L5） |
| POST | `/api/memory/session/{session_id}/summarize` | 强制刷新会话摘要 |
| GET | `/api/memory/dream-status/{client_id}` | AutoDream 闸门状态 |
| POST | `/api/memory/consolidate` | 手动触发休眠重塑（L6） |

---

## 六、配置项（`backend/.env`）

| 变量 | 默认 | 说明 |
|------|------|------|
| `MEMORY_SUMMARY_THRESHOLD` | `12` | 触发 L5 摘要的最小对话条数 |
| `AUTODREAM_MIN_HOURS` | `24` | L6 时间闸门（小时） |
| `AUTODREAM_MIN_SESSIONS` | `5` | L6 会话闸门 |
| `MEMORY_INDEX_MAX_LINES` | `200` | MEMORY.md 行数上限 |
| `MEMORY_INDEX_MAX_BYTES` | `25600` | MEMORY.md 体积上限（25KB） |

---

## 七、实现文件索引

| 文件 | 层级 |
|------|------|
| `CLAUDE.md` | L1 |
| `skills/resume-agent/SKILL.md` | L1 |
| `backend/app/services/session_store.py` | L2 |
| `backend/app/services/working_memory.py` | L3 |
| `backend/app/services/memdir.py` | L4 |
| `backend/app/services/user_memory.py` | L4（API 兼容层） |
| `backend/app/services/session_memory.py` | L5 |
| `backend/app/services/auto_dream.py` | L6 |
| `backend/app/services/agent_context.py` | 上下文拼装 |
| `backend/app/routers/memory.py` | HTTP 入口 |
