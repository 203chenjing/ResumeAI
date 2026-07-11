---

name: resume-agent

description: ResumeAI 动态 Agent 编排、编辑页交互、Human-in-the-loop、长期记忆。

metadata:

  version: "3.0.0"

---



# Resume Agent（动态规划）



## 设计原则



- **无写死流水线**：每步由 Planner 根据会话快照、用户输入、长期偏好与【当前可用工具】决定 specialist + action

- **工具注册表** `agent_registry.py`：按会话状态动态暴露 `analyze_jd`、`generate_suggestions` 等

- **上下文** `agent_context.py`：拼装 `PLANNER_SYSTEM` + 用户消息 + 记忆 + 近期对话

- **核心循环** `dynamic_agent.py`：orchestrate（上传页多步）/ chat（编辑页单轮）



## Specialist 角色（Planner 每步自选）



| 角色 | 典型职责 |

|------|----------|

| analyzer | JD / 匹配分析 |

| writer | 建议生成、知识库、偏好学习 |

| qa | 审阅、定稿、导出 |

| coordinator | 统筹任意当前可用工具 |



## Planner 输出 mode



| mode | 行为 |

|------|------|

| tool | 执行非高风险工具 |

| confirm | 高风险工具先征求用户确认 |

| chat | 编辑页对话改稿（NEW_SUGGESTIONS） |

| learn | 仅更新 `preference_updates` |

| finish | 结束并汇报 |



## Human-in-the-loop



需确认：`review_suggestions`、`finalize_resume`、`prepare_export`（由注册表 `risky` 标记驱动）



前端 `ConfirmDialog` + `confirmed_action` 重试。



## 长期记忆（六层架构）

参考晨 TR058485 · Claude Code 记忆子系统，详见 `docs/memory-architecture.md`。

| 层 | 名称 | ResumeAI 实现 |
|----|------|---------------|
| L1 | 指令记忆 | `CLAUDE.md` + `skills/` |
| L2 | 短期记忆 | `Session.chat_history`（零压缩） |
| L3 | 工作记忆 | `Session.working_memory` |
| L4 | 长期记忆 | `data/memdir/{client_id}/` + `MEMORY.md` |
| L5 | 摘要记忆 | `data/session_memory/{id}/summary.md` |
| L6 | 休眠重塑 | `auto_dream.py`（24h + 5 会话双闸门） |

## 长期记忆 API（L4 兼容层）



- `GET/PUT /api/user-memory/{client_id}`

- 偏好字段：`writing_style`、`review_policy`、`recent_intent`、`prefer_accept_safe`

- 会话级 `agent_prefs` 随交互更新



## API



| 路径 | 说明 |

|------|------|

| `POST /api/agent/run` | 上传页动态编排（SSE） |

| `POST /api/chat/agent` | 编辑页 Agent 对话（SSE） |

| `PUT /api/user-memory` | 保存长期记忆 |
| `GET /api/memory/index/{client_id}` | 读取 MEMORY.md 索引 |
| `POST /api/memory/consolidate` | 手动触发 AutoDream（L6） |


