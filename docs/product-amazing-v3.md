# ResumeAI v3 — Amazing 产品升级（Google 产品思维）

> 2026-06 | 北极星：**单日完成「发现→改稿→投递」闭环次数**

## 已落地能力

### 1. 数据飞轮（零 token）
- `behavior_signals`：记录 `tailor_start` / `apply_mark` / `dismiss_job` 等行为
- 从 `application_store` 推断常投公司、回避公司、偏好城市
- `match_engine.rerank_jobs` 接入 `behavior_profile` 动态加权
- 用户可 `PUT /api/hub/behavior/steer` 手动 boost/block 公司

### 2. 投递准备度（一个数字讲清该不该投）
- `readiness_score` = 匹配 × 截止紧迫 × 可信来源 × 内推码 × 是否已定制
- `GET /api/hub/readiness/{client_id}/{job_id}` + `explain` 可解释理由
- `POST /api/hub/readiness/rank` 按准备度排序

### 3. 30 秒 Aha
- 上传简历 `parse-resume` 返回 `aha`：Top3 + 一句结论
- Hub `TodayBriefingCard`：`GET /api/hub/today/{client_id}`

### 4. Deadline Agent
- 今日简报 `urgent_deadlines`：3 天内截止且未投递
- `followup_reminders` 合并岗位库截止提醒

### 5. ATS 回读
- 导出 PDF 后 `POST /api/hub/ats-readback`：pymupdf 提取 + 关键词保留率
- 前端 Export 页自动提示 ATS 分数

### 6. 批量 tailoring 预览
- `POST /api/hub/batch-tailor`：多岗位匹配 + gap + 行动建议（默认零 token）

### 7. 北极星漏斗埋点
- `funnel_metrics`：`job_view` → `job_tailor_start` → `export_pdf` → `apply_marked` → `loop_complete`
- `GET /api/hub/funnel/{client_id}` 转化率

### 8. 路由收敛
- `/upload` `/edit` `/export` `/knowledge` 已 redirect 至 studio/assets

### 9. 面试 → 知识库（已有增强）
- `mock_interview` score≥75 时 `extract_pending_from_diff` 写入 pending knowledge

## Google 原则对照

| 原则 | 落地 |
|------|------|
| Focus on task | Hub「今天投什么」单卡聚合 |
| Speed | 上传即 Aha，无需先爬全量 |
| Progressive disclosure | 准备度分解在 API，UI 只露总分+一句理由 |
| Trust | 可信徽章 + 行为可解释 `reasons` |
| Smart defaults | 飞轮从投递历史推断，越用越准 |

## 下一步（未做 / 需基建）

- 浏览器扩展 JD ingest（Phase C）
- 邮件自动识别投递状态（OAuth）
- 每日推送通知（Web Push / 邮件）
- GEval 回复质量评测（deepeval + DeepSeek judge）

## API 速查

```
GET  /api/hub/today/{client_id}
GET  /api/hub/aha/{client_id}
GET  /api/hub/readiness/{client_id}/{job_id}
POST /api/hub/readiness/rank
POST /api/hub/behavior/event
PUT  /api/hub/behavior/steer
POST /api/hub/batch-tailor
POST /api/hub/ats-readback
POST /api/hub/funnel/event
GET  /api/hub/funnel/{client_id}
```
