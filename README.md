# ResumeAI · AI 简历修改

> 面向求职者的 JD 驱动简历智能修改 Web 应用
> 上传简历、粘贴岗位 JD，AI 生成可审阅的修改建议并导出 A4 单页 PDF

---

## ✨ 核心能力

- **简历智能解析**：PDF / DOCX / Markdown / TXT 多格式上传，AI 结构化提取
- **JD 深度分析**：识别核心要求、加分项、关键词、行业术语 + **JD 真实性评分**（防假招聘）
- **匹配度评估**：5 维度量化评分（核心技能/经验/关键词/教育/软技能） + 差距分析
- **逐段修改建议**：每条建议含「原文 → 修改后 → 修改原因 → JD 匹配点」
- **双重多轮交互**：
  - **审批模式** — 接受 / 拒绝 / 调整每条建议
  - **聊天模式** — 自然语言指令（如「整体压缩到一页」）
- **A4 单页 PDF 导出**：标准版 / 修改痕迹版（含 diff 高亮）
- **真实性优先**：所有修改基于真实事实，缺数据自动占位 `[待补充]`，绝不编造

---

## 🚀 快速启动

### 前置依赖

| 工具 | 版本 |
| ---- | ---- |
| Python | 3.11+ |
| Node.js | 20+ |
| DeepSeek API Key | https://platform.deepseek.com |

### 方式 1：一键脚本（推荐）

**Windows:**
```bat
cd D:\需求文档\AI简历修改项目\demo
start.bat
```

**Linux / Mac:**
```bash
cd demo
chmod +x start.sh
./start.sh
```

首次运行会要求填写 `backend/.env` 中的 `DEEPSEEK_API_KEY`。

### 方式 2：Docker Compose

```bash
cd demo
cp backend/.env.example backend/.env
# 编辑 backend/.env 填写 DEEPSEEK_API_KEY
docker compose up -d
```

### 方式 3：手动启动

**后端**：
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

cp .env.example .env             # 编辑填入 DEEPSEEK_API_KEY
uvicorn app.main:app --reload --port 8000
```

**前端**（另开终端）：
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

访问 `http://localhost:3000`，API 文档 `http://localhost:8000/docs`。

---

## 🪟 Windows WeasyPrint 安装提示

WeasyPrint 在 Windows 需要 GTK3 运行库：
1. 下载安装 https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
2. 重启终端后 `pip install weasyprint`

如果安装困难，可临时改用 `playwright + Chromium` 渲染（修改 `services/pdf_exporter.py`）。

---

## 🗺 前端路由（Hub + Studio）

| 路径 | 说明 |
| ---- | ---- |
| `/` | Hub 工作台（继续改稿、待办、概览） |
| `/assets` | 知识库（三栏 + AI Copilot） |
| `/jobs` | 岗位发现（「用此 JD 改简历」） |
| `/tracker` | 投递追踪 |
| `/insights` | 求职洞察 |
| `/studio/prepare` | 改稿 · 准备（上传 + JD + 匹配） |
| `/studio/edit` | 改稿 · 编辑（预览 / 建议 / Copilot 三栏） |
| `/studio/export` | 改稿 · 导出（定稿 + 照片 + PDF + 记投递） |

**兼容重定向**：`/upload` → `/studio/prepare`，`/edit` → `/studio/edit`，`/export` → `/studio/export`，`/knowledge` → `/assets`。

**快捷键**：`⌘K` / `Ctrl+K` 命令面板；Studio 编辑页 `⌘J` / `Ctrl+J` 折叠 Copilot。

---

## 🗂 目录结构

```
demo/
├── README.md                          # 本文件
├── docker-compose.yml                 # 一键起 backend + frontend
├── start.bat / start.sh               # 一键启动脚本
│
├── backend/                           # FastAPI 后端
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── config.py                  # 配置
│   │   ├── routers/                   # 8 个 REST 路由
│   │   │   ├── resume.py              # POST /api/parse-resume
│   │   │   ├── jd.py                  # POST /api/analyze-jd
│   │   │   ├── analysis.py            # POST /api/analyze-match, /api/generate-suggestions
│   │   │   ├── suggestion.py          # POST /api/adjust-suggestion, /api/update-suggestion-status
│   │   │   ├── chat.py                # POST /api/chat (SSE)
│   │   │   ├── export.py              # POST /api/export-pdf, /api/preview-pdf
│   │   │   └── session.py             # GET /api/session/{id}
│   │   ├── services/                  # 业务逻辑
│   │   │   ├── llm_client.py          # LLM 客户端封装
│   │   │   ├── parser.py              # 简历解析
│   │   │   ├── jd_analyzer.py         # JD 分析
│   │   │   ├── match_analyzer.py      # 匹配度评分
│   │   │   ├── suggestion_engine.py   # 修改建议生成
│   │   │   ├── chat_engine.py         # 流式聊天
│   │   │   ├── pdf_exporter.py        # 调用 PDF 工具链
│   │   │   ├── md_builder.py          # 结构化 → Markdown 重建
│   │   │   └── session_store.py       # 内存会话管理
│   │   ├── models/schemas.py          # Pydantic 数据模型
│   │   ├── prompts/                   # 6 套 Prompt 模板
│   │   │   ├── parse_resume.py
│   │   │   ├── jd_analysis.py
│   │   │   ├── match_analysis.py
│   │   │   ├── suggestions.py
│   │   │   ├── chat_system.py
│   │   │   └── adjust.py
│   │   └── utils/file_handler.py
│   └── tools/                         # PDF 工具链
│       ├── markdown_resume_to_pdf.py  # MD → A4 单页 PDF
│       ├── check_resume_skill.py      # 格式自检
│       └── crop_profile_photo.py      # 照片裁剪
│
├── frontend/                          # Next.js 14 前端
│   ├── Dockerfile
│   ├── package.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                   # 首页
│   │   ├── upload/page.tsx            # → redirect /studio/prepare
│   │   ├── edit/page.tsx              # → redirect /studio/edit
│   │   ├── export/page.tsx            # → redirect /studio/export
│   │   ├── studio/prepare|edit|export # Studio 改稿流程
│   │   ├── assets/page.tsx            # 知识库 Object 视图
│   │   └── knowledge/page.tsx         # → redirect /assets
│   ├── components/
│   │   ├── layout/{AppShell,NavRail,TopBar,StudioHeader,CommandPalette}.tsx
│   │   ├── hub/{ContinueCard,TodoList,GlanceStats}.tsx
│   │   ├── studio/{PrepareView,EditView,ExportView}.tsx
│   │   ├── copilot/{CopilotPanel,KnowledgeCopilot}.tsx
│   │   └── edit/{ResumePreview,SuggestionPanel,SuggestionCard,ChatPanel}.tsx
│   ├── stores/useAppStore.ts          # Zustand 全局状态
│   └── lib/{api,types}.ts
│
└── skills/                            # 辅助 Skill 文件（供 AI Coding 工具使用）
    ├── resume-pdf-export/SKILL.md
    └── jd-analyzer/SKILL.md
```

> 主 Skill 文件 `SKILL.md`（简历改写完整规范）位于 `D:\需求文档\AI简历修改项目\SKILL.md`，未复制到 demo 内，由后端 prompts 直接复用其规则。

---

## 🎬 演示流程（评委视角）

1. 双击 `start.bat`（首次需填 API Key 后再启动一次）
2. 浏览器打开 `http://localhost:3000`
3. 拖拽 `测试简历.pdf` → 自动解析
4. 粘贴目标 JD → AI 分析需求 + 真实性评分
5. 点击「开始 AI 修改」
6. 编辑页：
   - **左**：简历实时预览
   - **中**：修改建议列表（接受/拒绝/调整）
   - **右**：AI 对话（输入「整体压缩到一页」）
7. 顶部「导出 PDF」→ 选择 标准版 / 修改痕迹版 → 下载

---

## 🧠 模型与 Prompt

- **模型**：DeepSeek (`deepseek-chat`)，temperature=0.3，json_object 输出
- **Prompt 体系**：6 套独立模板（解析/JD/匹配/建议/聊天/调整），核心规则源于 `SKILL.md` 中的 STAR 法则、JD 匹配规范、量化指标处理、不编造原则
- **流式响应**：聊天接口走 SSE，前端 fetch + ReadableStream 解析
- **会话**：内存字典，30 分钟无操作自动清理

---

## 📄 API 接口

| 路径 | 方法 | 说明 |
| ---- | ---- | ---- |
| `/api/parse-resume` | POST | 上传 + 解析简历 |
| `/api/analyze-jd` | POST | JD 分析（含真实性） |
| `/api/analyze-match` | POST | 匹配度评分 |
| `/api/generate-suggestions` | POST | 生成修改建议 |
| `/api/update-suggestion-status` | POST | 接受/拒绝/撤销 |
| `/api/adjust-suggestion` | POST | 调整单条建议 |
| `/api/chat` | POST (SSE) | 流式聊天 |
| `/api/export-pdf` | POST | 导出 PDF |
| `/api/preview-pdf` | POST | 生成 PDF 预览 |
| `/api/download/{filename}` | GET | 下载 PDF |
| `/api/session/{id}` | GET | 查询会话状态 |
| `/api/knowledge-agent/init-from-resume` | POST | 从简历初始化知识库 |
| `/api/knowledge-agent/expand-star` | POST | 补全 STAR 段落 |
| `/api/knowledge-agent/audit` | POST | 审计知识库 |
| `/api/knowledge-agent/chat` | POST | 知识库 Copilot 对话 |

完整 OpenAPI 文档：`http://localhost:8000/docs`

---

## 🔒 数据隐私

- 简历内容仅存内存，**不持久化**
- 30 分钟无操作自动清理
- LLM 请求通过 HTTPS 直连 DeepSeek 官方接口
- 不收集任何个人数据

---

## 🛠 待用户配置

- **DEEPSEEK_API_KEY**：填入 `backend/.env` 后启动
- 可选：`backend/exports/` 是 PDF 输出目录
- 可选：自定义模型 ID（默认 `deepseek-chat`，支持 `deepseek-reasoner` 切换）

---

## 📝 说明

本产品面向 C 端求职者使用。示例简历与知识库均为虚构占位内容，请勿将仓库内样例当作真实个人信息。

---

## 🧪 测试

确保产品可用：本地一键跑 **单元测试 + 冒烟 + 前端构建**（无需 LLM API Key）。

```bat
cd demo
run_tests.bat
```

| 层级 | 命令 | 需要 API Key |
| ---- | ---- | ------------ |
| 单元测试 | `cd backend && pytest` | 否 |
| API 冒烟 | `python backend/scripts/smoke_test.py` | 否 |
| 全流程 E2E | 先启动后端，再 `python backend/scripts/e2e_full_test.py` | 是 |
| 前端 | `cd frontend && npm run lint && npm run build` | 否 |

详细策略见 [docs/TESTING.md](docs/TESTING.md)；手工用例见上级目录 [测试文档.md](../测试文档.md)。

CI：推送 `demo/**` 变更时 GitHub Actions 自动跑 pytest + smoke + frontend build。
