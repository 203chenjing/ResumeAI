# ResumeAI 测试体系

> 目标：**无 API Key 也能在 CI 通过**；有 Key 时跑完整 LLM 端到端；发布前人工走查清单兜底。

对标：[career-ops `test-all.mjs`](https://github.com/santifer/career-ops)（63+ 检查）、[Resume-Matcher](https://github.com/srbhr/Resume-Matcher)（ATS 评分回归）、[job-ops](https://github.com/DaKheera47/job-ops)（CI + Docker 自测）。

---

## 测试金字塔

```
                    ┌─────────────────┐
                    │  人工验收清单    │  发布前 / 参赛演示前
                    └────────┬────────┘
               ┌─────────────┴─────────────┐
               │  E2E 全流程 (需 LLM Key)   │  e2e_full_test.py
               └─────────────┬─────────────┘
          ┌──────────────────┴──────────────────┐
          │  API 冒烟 + Golden Prompt Eval       │  smoke_test.py + eval/
          └──────────────────┬──────────────────┘
     ┌───────────────────────┴───────────────────────┐
     │  单元测试 pytest（无 LLM、无网络）              │  backend/tests/
     └───────────────────────────────────────────────┘
```

| 层级 | 命令 | 需要 API Key | 耗时 |
|------|------|--------------|------|
| L1 单元 | `cd backend && pytest` | 否 | ~10s |
| L2 冒烟 | `python scripts/smoke_test.py` | 否 | ~5s |
| L3 Golden | `python scripts/eval_prompts.py` | 可选（无 Key 跳过 LLM） | ~1min |
| L4 E2E | `python scripts/e2e_full_test.py` | 是 | 3–8min |
| L5 前端 | `cd frontend && npm run build && npm run lint` | 否 | ~2min |
| L6 人工 | 见 [测试文档.md](../../测试文档.md) | 演示前 | — |

**一键本地：**

```bash
cd demo
# Windows
run_tests.bat
# Linux/Mac
./run_tests.sh
```

---

## L1：单元测试（`backend/tests/`）

覆盖 **不依赖 LLM** 的核心逻辑：

| 文件 | 覆盖 |
|------|------|
| `test_health.py` | `/health`、`/` 路由 |
| `test_session_store.py` | 创建/获取/过期清理 |
| `test_suggestion_apply.py` | 接受/拒绝/撤销替换逻辑 |
| `test_resume_density.py` | 稀疏/适中/过密阈值 |
| `test_user_memory.py` | 读写/偏好合并 |
| `test_check_resume_skill.py` | SKILL 格式校验（合法/非法样例） |
| `test_knowledge_api.py` | 知识库模板 API（无 LLM） |

原则（借鉴 career-ops）：
- 每个 PR **必须**通过 L1 + L2 + L5
- 不 mock 整个业务；只 mock LLM 客户端（后续 `eval/` 使用）

---

## L2：API 冒烟（`scripts/smoke_test.py`）

启动方式：使用 `TestClient` 进程内调用，**无需**先 `uvicorn`。

检查项：
- 健康检查 200
- 知识库模板非空
- 非法 session 返回 404/错误
- 空 JD 请求被拒绝
- user-memory CRUD 往返

---

## L3：Golden 数据集（`backend/tests/fixtures/golden/`）

| 文件 | 用途 |
|------|------|
| `resume_valid.md` | 应通过 `check_resume_skill` |
| `resume_invalid_skills.md` | 应失败（技能行数不对） |
| `jd_campus_pm.txt` | 标准秋招管培 JD |
| `jd_ai_pm.txt` | AI 产品实习 JD |
| `expected_match_bounds.json` | 匹配分合理区间（E2E 断言用） |

`eval_prompts.py`（规划项，E2E 已部分覆盖）：
- 结构化断言：JSON schema、字段非空、分数区间
- **不断言** LLM 文案一字不差（避免 flaky）

---

## L4：端到端（`scripts/e2e_full_test.py`）

前置：`uvicorn app.main:app --port 8000` + `DEEPSEEK_API_KEY`。

流程：PDF 解析 → 知识库 → JD → 匹配 → 建议 → 接受 → 定稿 → 导出 PDF。

输出：`scripts/e2e_report.json`，CI 可上传 artifact。

通过条件：`report.passed == true` 且 `checks` 全部 `ok`。

---

## L5：前端

```bash
cd frontend
npm run lint
npm run build
```

后续 V2.0 增加 Playwright UI 测试（对标 job-ops / career-ops Playwright 用法）。

---

## CI（`.github/workflows/resumeai-demo-ci.yml`）

每次 PR / push 到 `main`（`AI简历修改项目/demo/**` 变更时）：

1. Backend: `pip install -r requirements.txt -r requirements-dev.txt && pytest`
2. Backend: `python scripts/smoke_test.py`
3. Frontend: `npm ci && npm run lint && npm run build`

**不**在默认 CI 跑 E2E（避免泄露 Key、成本高）。可选 `workflow_dispatch` 手动触发 E2E。

---

## 发布 / 演示前人工清单（摘自测试文档）

最小必测路径（5 分钟）：

1. 上传 `test-resume.md` 或示例 PDF → 解析成功
2. 粘贴 `test-jd.txt` → JD 分析有关键词
3. 开始修改 → 至少 1 条建议可接受/拒绝
4. 定稿 → 校验通过
5. 导出 PDF → 单页、可打开

完整用例见 [测试文档.md](../../测试文档.md)（F-001 ~ P-007）。

---

## V2.0 模块测试扩展（规划）

| 新模块 | 测试策略 |
|--------|----------|
| 知识库 2.0 | 文章 CRUD、revision diff、PendingChange 审批 |
| 追踪器 | 状态机非法转移拒绝、漏斗统计快照 |
| 爬虫 | Provider mock HTML fixture、去重、限速 |
| 模拟面试 | STAR 评分函数单元测试 + 固定问答 golden |
| 多 JD 对比 | 批量评估结果排序稳定性 |

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `pytest` 找不到 `app` | 在 `backend/` 目录执行，或 `PYTHONPATH=.` |
| E2E 定稿失败 | 查看 `e2e_report.json` 的 `validation`；多为字数过少 |
| PDF 导出 0 页 | 检查 WeasyPrint/Playwright 依赖 |
| CI 前端 build 失败 | 本地 `npm run build` 复现 |
