# 开源对标索引

实现各模块前查阅本表，记录「复用什么 / 改什么」。不直接 fork 整仓；保留 ResumeAI 中文 SKILL 与 A4 PDF 工具链。

| 模块 | 仓库 | Stars | 复用要点 | 许可 |
|------|------|-------|----------|------|
| 求职全链路 | [career-ops](https://github.com/santifer/career-ops) | ~55k | oferta、states.yml、story-bank、scan、DATA_CONTRACT | MIT |
| 母版+匹配 | [Resume-Matcher](https://github.com/srbhr/Resume-Matcher) | ~27k | Master Resume、ATS 分、匹配 UI | Apache-2.0 |
| 追踪看板 | [job-ops](https://github.com/DaKheera47/job-ops) | ~3.3k | Kanban、漏斗、管道 UI | 自托管 |
| 爬虫 | [JobSpy](https://github.com/speedyapply/JobSpy) | ~3.7k | Provider 模式、字段标准化 | MIT |
| 知识库 CMS | [noosphere](https://github.com/SweetSophia/noosphere) | — | 文章+版本+Topic | Apache-2.0 |
| 编辑器 | [Novel](https://github.com/steven-tey/novel) | ~16k | TipTap Notion 风 | Apache-2.0 |
| 审批门 | [llm-wiki](https://github.com/ddsyasas/llm-wiki) | — | pending → confirm | MIT |
| 测试 CI | career-ops `test-all.mjs` | — | 多层检查、PR 门禁 | MIT |

## 本仓库映射

| ResumeAI 路径 | 对标 |
|---------------|------|
| `backend/app/services/session_store.py` | resume-lm 持久化 |
| `backend/app/services/application_advisor.py` | career-ops oferta 分档 |
| `backend/app/services/pending_knowledge.py` | llm-wiki approval gate |
| `backend/app/routers/applications.py` | job-ops tracker + career-ops states.yml |
| `frontend/components/match/*` | Resume-Matcher 评分展示 |
| `frontend/app/tracker/*` | job-ops dashboard |
| `backend/tests/` + `docs/TESTING.md` | career-ops test-all |
