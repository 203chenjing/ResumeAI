# ResumeAI 工程与产品体检（2026-10）

> 体检方式：本地从零部署（Python 3.11 venv + Next 生产构建）→ 真实 DeepSeek Key 跑通「解析 → 岗析 → 匹配 → 建议 → 定稿 → 导出 PDF」→ 通读 16k 行后端 / 10k 行前端关键路径。
> 结论先行：**产品设计是站得住的（知识库为源、岗位为压缩目标、人控 AI），但工程状态与 README 描述有明显落差——CI 连续 7 次红灯、核心「一键改稿」链路存在必崩的 NameError、Docker 与 PDF 导出在干净环境不可用、Next.js 固定在一个已知可 RCE 的版本。**

---

## 一、本次已修（含复现与验证）

按影响面排序。每条都写了「为什么是问题」，方便复盘。

### P0-1 「一键改稿」主链路 500：`assess_density` 未导入

- **现象**：`POST /api/generate-suggestions` 稳定 500，前端只看到「服务内部错误」。
- **根因**：`services/suggestion_engine.py` 的 `_filter_suggestions_by_density` 调用了 `assess_density`，但模块顶部没有导入 → `NameError`。
- **为什么没被测试拦住**：194 个单测里没有一条覆盖这个过滤函数；真实链路也没进 CI。
- **修复**：补导入；新增 `tests/test_suggestion_density_filter.py`（稀疏简历不删内容 / 密集简历最多删两条 / 非 delete 建议不受影响）。
- **验证**：真实 Key 下建议生成从 500 → 200，返回 11 条建议。

### P0-2 CI 自 2026-07 起连续红灯（7 次失败）

四个失败的测试，两类原因：

| 测试 | 真实原因 | 处理 |
|------|---------|------|
| `test_resume_from_knowledge::test_build_resume_empty_kb_raises` | 单测会回退到仓库内 `memory/` 的知识库并**真打 DeepSeek**，CI 无 Key → 401 | 用 monkeypatch 隔离 L4 记忆回退，测试变 hermetic |
| `test_pending_knowledge::test_extract_and_confirm` | 产品后来加了「确认必须选归属经历」的约束，测试没跟上 | 补 `target_title`；另加两条回归测试（缺标题报错、忽略不需要标题） |
| `test_resume_list_format::test_preserve_number_from_reference` | `ensure_experience_item_format` 承诺输出 `N. **标题**：正文`，但「无标题、编号来自 reference」时会退化成 `2. 正文` | 代码补齐：仅当编号借用自 reference 时才借用其标题（避免把别的 bullet 标题套错） |
| `test_suggestion_anchor::test_find_line_range` | 建议文本带旧编号 `1.`、简历里是 `2.`，严格匹配返回 `[0,0]`；且原断言行号写错 | 定位逻辑改为忽略列表编号；测试断言改为「命中的行确实包含快筛」 |

**验证**：`pytest` 194 passed / 1 skipped；`smoke_test.py`、`prompt_eval.py` 全绿。

### P0-3 Next.js 安全版本

- 固定 `next@14.2.15`，`npm audit` 报 1 critical + 14 high。其中两条 critical 是**未鉴权 RCE**：
  - `GHSA-p293` Windows 自托管服务器 RCE
  - `GHSA-2xp9` Image Optimization API（AVIF）RCE
- **处理**：升到 `14.2.35`（14.x 最新补丁，零 breaking）；本项目不使用 `next/image`，顺手在 `next.config.js` 关掉图片优化接口（`images.unoptimized`），收掉 AVIF 链路攻击面；同时关闭 `X-Powered-By`。
- **遗留**：Next 14 仍有 1 critical + 若干 high，官方只在 Next 16 修复 → **升级 Next 16 是本项目最大的未偿技术债**（见路线图 P0）。

### P1-1 未配置 Key 时给出 500 + 堆栈

- **现象**：`backend/.env` 没填 Key 时，`parse-resume` 返回 500 和一大段 traceback；客户端用占位串 `DEMO_KEY` 请求 DeepSeek，把「配置缺失」伪装成「上游 401」。
- **修复**：
  - `llm_client` 不再用占位 Key，缺 Key 抛 `LLMNotConfiguredError`；
  - 全局异常处理：配置缺失 → `503 {code: llm_not_configured}`；上游 4xx/5xx → `502`；未知异常 → `500` 且**对外只给一句可读提示**，堆栈只进日志；
  - `/health` 增加 `llm_configured` 字段，部署后一眼判断 Key 是否生效。
- **验证**：无 Key 时返回 `503 {"code":"llm_not_configured","detail":"未配置 DEEPSEEK_API_KEY..."}`；补 Key 后 `llm_configured: true`。

### P1-2 LLM 调用层的三个工程问题

| 问题 | 影响 | 修复 |
|------|------|------|
| 每次请求新建 `httpx.AsyncClient` | 无法复用连接，改稿一次 5+ 次调用，TLS 握手重复付费 | 进程内共享连接池（20 连接 / 10 keep-alive），lifespan 关闭时释放 |
| 只对 429 重试 | 502/503/超时直接失败，用户看到「改稿失败」但其实是瞬时故障 | 统一对 408/429/5xx/超时做指数退避 + 抖动（最多 3 次） |
| 无用量日志 | 不知道一次改稿烧多少 token，无法做成本优化 | 每次调用记录 `prompt_tokens/completion_tokens` |

新增 `tests/test_llm_client.py`：缺 Key 报错、503 重试后成功、401 转友好文案、非法 JSON 重试后报错。

### P1-3 导出文件名可目录穿越（任意文件写入/读取）

- `payload.filename` 直接拼进 `exports/`：`..\..\backend\.env` 可写穿；`C:\Windows\x.pdf` 因 pathlib 绝对路径语义可写到任意位置；`GET /api/download/{filename}` 同理可**读**任意文件。
- **修复**：`safe_export_filename()` 统一收敛（去目录、替换 Windows 保留字符、补 `.pdf`、截断保后缀），download 路由再校验 `resolve()` 必须落在 `exports/` 内。
- **验证**：`GET /api/download/..%5C..%5Cbackend%5C.env` → 404；`tests/test_export_filename.py` 6 条用例覆盖。

### P1-4 PDF 渲染失败时把 traceback 抛给用户

- 定稿/导出在 Chromium 缺失时，`layout_issues` 直接塞进 Python 堆栈（含本机绝对路径），前端显示「定稿未通过校验：Traceback ...」。
- **修复**：`_tool_failure_message()` 把工具输出收敛成一句话；识别 `Executable doesn't exist` 时直接提示 `python -m playwright install chromium`。

### P2-1 Docker 部署在本机/CI 都跑不起来

| 问题 | 后果 |
|------|------|
| `frontend/Dockerfile` `COPY --from=builder /app/public ./public`，但仓库**没有 `public/` 目录** | `docker build` 直接失败 |
| `backend/Dockerfile` 装了 WeasyPrint 的系统依赖，但项目根本不用 WeasyPrint（导出走 Playwright） | 镜像白白变大，且误导维护者 |
| `backend/Dockerfile` 没有 `playwright install` | 容器里「定稿/导出 PDF」必然失败 |
| 前端用 `npm install` 而非 `npm ci` | 构建不可复现 |
| 两个服务都没有 healthcheck，`depends_on` 只是启动顺序 | 前端比后端先起，首屏请求全 500 |
| `version: "3.9"` | 新版 Compose 已废弃 |

**修复**：补 `public/.gitkeep`、`npm ci`、镜像内装 Chromium、删掉无用系统依赖、加 healthcheck 与 `service_healthy` 依赖、去掉废弃字段，并新增前后端 `.dockerignore`。

### P2-2 写死了开发机的个人绝对路径

`interview_bank.py` 与 `qiuzhao_system.py` 都把面经库指向 `D:/Users/<user>/Downloads/...`。换台机器 → 面经库静默为空，用户以为「这个功能没做」。

**修复**：新增 `QIUZHAO_DB_PATH` 配置，默认 `backend/data/qiuzhao.db`；缺失时按「未启用」处理。

### P2-3 其它

- `run_server.py` 写死 `0.0.0.0:8000` + `reload=True`，`.env` 里的 `HOST/PORT/DEBUG` 完全不生效 → 改为读配置。
- 待确认知识接口把「参数错误」返回 404（语义错误，前端无法区分「不存在」和「没选归属经历」）→ 拆成 400/404。
- README 的「102+ 单元测试」「WeasyPrint」与实际不符 → 改为 190+/Playwright；补 Docker 部署与常见问题排障表；补 `LICENSE`（README 声称 MIT 但仓库没有 LICENSE 文件）。

---

## 二、还能怎么优化（按 ROI 排序，尚未实施）

### P0 · 安全与合规

1. **Next 16 迁移**（剩余 critical 只能靠大版本解决）。建议步骤：先锁 `next@15.5.x` 验证构建 → 再上 16；重点检查 App Router 的 async params、`next lint` 迁到 ESLint flat config。
2. **后端零鉴权**：8000 端口对同网段任何人开放，`/api/download` 可枚举、`client_id` 由前端自造。若只做本机单人工具，至少：默认 `HOST=127.0.0.1`、CORS 白名单、`/api/download` 加一次性 token；若要多人用，补一层轻量 API Key 或 OAuth。
3. **上传文件校验**：现在只看大小。<10MB 的任意文件都会进解析器，建议校验 MIME + magic bytes，并限制 `pdf/docx/md/txt`。

### P1 · 可靠性与成本

4. **会话全内存**：`session_store` 重启即丢，用户改到一半刷新电脑就归零。建议 SQLite 持久化（已有 `data/` 目录与归档结构，改造成本不高）。
5. **LLM 结果缓存**：同 JD + 同简历的「岗析/匹配」结果可缓存（JD hash 命中率在校招场景很高），能把单次改稿成本降 30%-50%。
6. **把真链路 e2e 放进 CI nightly**：这次的 NameError 是「测试全绿 + 主流程全崩」的典型。用 1 条固定简历 + 1 条固定 JD 跑完整链路（约 15-20s，成本可忽略），失败即告警。
7. **降级策略**：Key 失效/限流时，解析可退回本地规则解析（已有 `md_builder`），不要整条链路不可用。

### P1 · 解析器会丢掉非标准章节（数据丢失）

真机验证时发现：上传的简历里 `## 荣誉奖励`、`## 自我评价` 两节，经 `/api/parse-resume` 后**整节消失**，只剩「教育 / 实习 / 项目 / 技能」四节。解析 Prompt 用的是固定 schema，未列入的章节被静默丢弃。

- 影响：用户看到的是「我的简历怎么少了一段」，且没有任何提示。
- 建议：① 解析结果增加 `unknown_sections` 字段并在「准备」页提示「以下内容未纳入标准结构，可移入知识库」；② 或把剩余章节统一收进 `## 其他`。

### P2 · 定稿闸门「页底留白 ≤20mm」偏严

`MAX_BOTTOM_GAP_MM = 20`，实测一份 2000 字、12 条 bullet 的完整一页简历仍测得 30mm，被拦在定稿前（提示「建议补充经历或返回改稿」），但实际版面观感是正常的。

- 建议：阈值放宽到 25-30mm，或把「留白偏多」降级为**提示**而非**阻断**（真正阻断的只保留：超过 1 页、Skill 校验不通过）。
- 这条属于产品判断，本次未擅自修改。

### P2 · 产品体验


8. **改稿进度可视化**：现在是一次 POST 等到底，用户盯着转圈 30s+。建议把「岗析 → 匹配 → 建议」改成分步 SSE 推送（前端已有 `ThinkChainPanel`，接上即可）。
9. **建议批量操作**：11 条建议逐条点「接受/拒绝」很累；加「全部接受安全建议（wording/keyword）」一键，风险项仍逐条确认。
10. **知识库待确认三套组件合一**：`PendingKnowledgePanel`、`KnowledgePendingPanel`、`KnowledgePendingWorkspace` 三套并存，其中前两套的确认按钮是 disabled 的占位实现。留一套，删两套。
11. **匹配分可解释**：五维雷达图目前只有分数，缺「哪条经历支撑了这个维度」的证据锚点，招人方视角下这是最容易被追问的点。

### P3 · 工程卫生

12. **服务按域收敛**：`services/` 已有 60+ 文件，其中 `job_*` 9 个、`knowledge_*` 5 个。建议拆成 `app/domains/jobs/`、`app/domains/knowledge/`，routers 只做编排。
13. **前端类型严格化**：`lib/types.ts` 大量可选字段 + `any` 逃逸（如 GenUiRenderer），建议开 `noUncheckedIndexedAccess` 并给 API 响应生成类型。
14. **结构化日志 + request_id**：现在慢请求会打一条 warning（本次新增 `SLOW_REQUEST_SECONDS`），但没有 request_id 串起一次改稿的多条日志。
15. **文档索引**：`docs/` 已有 8 篇设计文档，建议在 README 或 `docs/README.md` 给一张「读哪篇解决什么问题」的索引。

---

## 三、验证记录

| 项目 | 命令 | 结果 |
|------|------|------|
| 后端单测 | `pytest -q` | 194 passed, 1 skipped |
| API 冒烟 | `python scripts/smoke_test.py` | ALL SMOKE CHECKS PASSED |
| Prompt/规则评测 | `python scripts/prompt_eval.py` | ALL EVAL CHECKS PASSED |
| 前端生产构建 | `npm run build` | 16 条路由编译通过 |
| 前端 lint | `npm run lint` | 0 error（5 条 exhaustive-deps warning，历史遗留） |
| 依赖安全 | `npm audit` | critical 从 2 条降到 0 条可修项（剩余需 Next 16） |

真实链路（真实 DeepSeek Key，端到端约 15-80s，随内容长度浮动）：

| 步骤 | 结果 |
|------|------|
| `POST /api/parse-resume` | 200，产出 2000 字结构化 Markdown |
| `POST /api/analyze-jd` | 200，岗位要求 / 关键词 / 可信度 |
| `POST /api/analyze-match` | 200，五维匹配 + 差距 + 投递建议 |
| `POST /api/generate-suggestions` | 200，11 条建议（修复前此处稳定 500） |
| `POST /api/update-suggestion-status` | 200，逐条 accept/reject 生效 |
| `POST /api/finalize-resume` | 400「页底留白约 30mm」——**产品闸门按设计拦截**，非崩溃 |
| PDF 渲染（直接调用 `tools/markdown_resume_to_pdf.py`） | 1 页 A4、Skill 校验通过，版面正常 |

> 定稿闸门阈值未改动，属产品判断，已在「还能怎么优化」中列为待决策项。

---

## 四、一句话总结

这个项目的问题不在「想法」，而在**主链路的工程可信度**：核心功能会 500、CI 红了一个季度、部署路径在干净机器上走不通。本次把这些堵点全部打通并补了针对性回归测试；下一步最该做的是 **Next 16 安全升级 + 会话持久化 + 真链路 nightly e2e**，这三件做完，「个人 AI 改简历工具」才真正具备可交付的稳定性。
