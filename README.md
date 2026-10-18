# ResumeAI

**把简历改到能投** — 面向求职者的 AI 简历工作台：针对目标岗位改稿、一页 PDF 直接投递，并串联岗位发现与投递追踪。

[![CI](https://github.com/203chenjing/ResumeAI/actions/workflows/ci.yml/badge.svg)](https://github.com/203chenjing/ResumeAI/actions/workflows/ci.yml)

---

## 为什么选 ResumeAI？

市面上很多「AI 改简历」只做一件事：把简历扔给模型，直接改一版。ResumeAI 的设计思路不同 — **以知识库为素材源、以岗位为压缩目标、以你的确认为最终裁决**，把「改简历」做成一条可重复、可追踪的求职流水线。

### 核心优势

| 优势 | 说明 |
|------|------|
| **一站闭环** | 工作台 → 准备 → 改稿 → 导出 PDF → 记入投递追踪 → 面试准备，不必在多个工具间来回倒腾 |
| **知识库驱动** | 经历素材沉淀在知识库，换岗位时从知识库生成投递版简历，而不是每次从零改 Word |
| **一键改稿 + 可见进度** | 分析岗位 → 算匹配度 → 出建议，三步链路一次完成，进度实时展示 |
| **人控 AI、不瞎编** | 每条建议可采纳 / 跳过 / 微调；缺数据标 `[待补充]`，不伪造经历与指标 |
| **岗位可信度 + 匹配评分** | JD 真实性评分防假招聘；五维匹配 + 差距分析，知道差在哪、先改什么 |
| **GUI + LUI 双模交互** | 列表点选为主路径，对话微调为辅；助手可驱动左侧预览与建议列表同步更新 |
| **投递级 PDF** | A4 单页、关键词加粗、版面留白检测、证件照裁剪；支持标准版 / 修改痕迹版 |
| **校招场景增强** | 多源岗位聚合（GitHub 校招库 / 企业 ATS / 高校就业网）、岗位对比、投递看板、拒信模式洞察、模拟面试 |
| **工程可验证** | 后端 **190+** 单元测试，CI 自动跑 pytest + 冒烟 + 前端构建与 lint |

### 和「只聊天改简历」的差异

```
普通工具：  上传简历 → AI 直接改 → 下载（难复盘、难复用、难追踪）

ResumeAI：  知识库积累素材
              ↓
            贴岗位描述 → 匹配分析 → 逐条建议确认
              ↓
            定稿导出 PDF → 投递追踪 → 面试准备
```

---

## 功能一览

- **简历解析**：PDF / DOCX / Markdown / TXT
- **岗位分析**：核心要求、关键词、行业术语、可信度评分
- **匹配评估**：雷达图 + 差距列表 + 投递建议
- **修改建议**：措辞 / STAR 改写 / 关键词嵌入 / 结构调整，附原因与岗位匹配点
- **知识库**：结构化编辑 + 整理助手（导入、补全、核对待填项）
- **从知识库生成简历**：按当前岗位从素材库压缩出一页投递版
- **一页预算**：改稿页常驻容量仪表（字数 / 预计页数 / 条数 / 技能条数），采纳建议时标注 `+N 字`
- **定稿预检**：进入导出页即体检，问题带动作（AI 压到一页 / 去改稿 / 仍然按 N 页导出），不在最后一步才打回
- **一键局部压缩**：只压缩最长的几条 bullet 并逐条可撤销，不重写整篇
- **导出**：定稿闸门、撤销定稿、版面检查、自动记入投递
- **岗位**：筛选、对比、求职偏好；**选岗 Copilot**（DeepSeek tool-calling）；**Hub 今日卡**（准备度排序、截止提醒、行为飞轮个性化）
- **投递追踪**：看板 / 表格、转化漏斗、跟进提醒
- **求职洞察**：档案、拒信模式、策略建议

---

## 快速启动

### 依赖

| 工具 | 版本 |
|------|------|
| Python | 3.11+ |
| Node.js | 20+ |
| DeepSeek API Key | [platform.deepseek.com](https://platform.deepseek.com) |

### 一键启动（推荐）

**Windows**

```bat
start.bat
```

**Linux / macOS**

```bash
chmod +x start.sh
./start.sh
```

首次运行会提示配置 `backend/.env` 中的 `DEEPSEEK_API_KEY`。

### 手动启动

**后端**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 填入 DEEPSEEK_API_KEY
python run_server.py        # http://localhost:8000
```

**前端**

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                   # http://localhost:3000
```

API 文档：`http://localhost:8000/docs`

> 导出 PDF 依赖 Chromium：首次使用前在 `backend` 目录执行
> `python -m playwright install chromium`（约 200MB，只需一次）。

### Docker 部署

```bash
cp backend/.env.example backend/.env   # 填入 DEEPSEEK_API_KEY
docker compose up -d --build
```

- 后端镜像已内置 Chromium，导出 PDF 开箱可用
- 前端 `NEXT_PUBLIC_API_URL` 在 **build 阶段**固化，换地址需 `docker compose build frontend`
- 健康检查：`curl http://localhost:8000/health` 应返回 `"llm_configured": true`

### 常见问题

| 现象 | 原因与处理 |
|------|-----------|
| 接口返回 `503 llm_not_configured` | `backend/.env` 未填 `DEEPSEEK_API_KEY`（或填错），补齐后重启后端 |
| 接口返回 `502 llm_upstream_error` | DeepSeek 侧限流/故障；客户端已自动重试 3 次，仍失败看后端日志 |
| 定稿/导出报「PDF 渲染组件不可用」 | 未安装 Chromium：`python -m playwright install chromium` |
| 页面一直转圈 | 后端未启动或 CORS 不匹配；先看 `http://127.0.0.1:8000/health` |
| 端口被占用 | `start.bat` 会自动清理 8000/3000；手动启动需先结束旧进程 |


---

## 推荐使用路径

1. **工作台** — 继续上次改稿，或「开始改简历」
2. **准备** — 上传简历 + 粘贴岗位描述 → **一键改稿**
3. **改稿** — 预览左、建议中、可选「微调」右；工具栏常驻「一页容量」仪表，超预算当场可见
4. **导出** — 先看「定稿预检」：通过则定稿；未通过可「AI 压到一页」「去改稿」或「仍然按 N 页导出」
5. **（可选）知识库 / 岗位 / 追踪** — 长期沉淀素材、选岗、跟进进度

---

## 前端路由

| 路径 | 说明 |
|------|------|
| `/` | 工作台 |
| `/studio/prepare` | 准备（上传 + 岗位 + 一键改稿） |
| `/studio/edit` | 改稿（预览 / 建议 / 微调） |
| `/studio/export` | 导出（定稿 + PDF） |
| `/assets` | 知识库 |
| `/jobs` | 岗位发现 |
| `/tracker` | 投递追踪 |
| `/insights` | 求职洞察 |

兼容重定向：`/upload` → prepare，`/edit` → edit，`/export` → export，`/knowledge` → assets。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 14 · React 18 · Zustand · Tailwind |
| 后端 | FastAPI · Pydantic · DeepSeek API |
| PDF | Playwright + Chromium · 自研 Markdown → A4 排版 |
| 测试 | pytest（102+）· GitHub Actions CI |

产品设计参考 Google Material 信息架构：**单一主路径、渐进披露、AI 提案 + 人决策**。文案与样式集中在 `frontend/lib/copy.ts` 与 `globals.css` 设计 token。

---

## 目录结构

```
ResumeAI/
├── start.bat / start.sh          # 一键启动
├── CLAUDE.md                     # L1 指令记忆
├── memory/                         # memdir 模板（MEMORY.md + topics）
├── docs/memory-architecture.md     # 六层记忆架构说明
├── backend/                      # FastAPI
│   ├── app/routers/              # REST + Agent 路由
│   ├── app/services/             # 解析、匹配、建议、知识库、PDF…
│   ├── app/prompts/              # Prompt 模板
│   ├── tests/                    # 单元测试
│   └── tools/                    # PDF 工具链
├── frontend/                     # Next.js
│   ├── app/                      # 页面路由
│   ├── components/               # Studio / Hub / Copilot…
│   └── lib/copy.ts               # 产品文案
└── .github/workflows/ci.yml      # CI
```

---

## 测试

```bash
# 后端（无需 API Key）
cd backend && pytest -q

# 前端
cd frontend && npm run build
```

推送 `main` 分支时 GitHub Actions 自动执行 pytest、API 冒烟与前端构建。

---

## 配置说明

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | 必填，LLM 调用与岗位 AI 解析/打标签；未配置时 AI 接口返回 503 |
| `CRAWL_SCHEDULE_ENABLED` | 可选，设为 `true` 开启每日定时抓取（默认开启） |
| `QIUZHAO_DB_PATH` | 可选，外部秋招聚合库 `qiuzhao.db` 路径（默认 `backend/data/qiuzhao.db`） |

勿将 `backend/.env` 提交到 Git。

### 岗位数据源（`backend/crawl_sources.yml`）

> 聚焦**国内岗位（含在华外企）**。海外仓库默认关闭，可按需用 `china_only` 过滤后启用。

| Provider | 说明 | 成本 |
|---|---|---|
| `github_joblist` | 国内每日校招仓库（namewyf/Campus2026、0voice 计算机校招汇总），含外企中国分部，自带官方投递链接与内推码；支持「章节标题即公司」的表格结构 | 零 token，无浏览器 |
| `ats_board` | 在华外企官方 ATS 公开 JSON 接口（Greenhouse / Lever / Ashby），`china_only` 仅保留中国大陆岗位 | 零 token，无浏览器 |
| `university_html` | 北上广深及重点高校就业网 | HTTP/Playwright |
| `qiuzhao_system` | **本地秋招聚合系统**（搜狗微信/牛客/智联校招/前程无忧/实习僧等已清洗 27 届岗位库，直接读取 SQLite，无需网络请求；来源含 51job/yingjiesheng 时由 blocked_domains 合规过滤） | 零 token，无浏览器 |
| `company_campus` / `job_aggregator` | 企业校招页与聚合站（牛客等） | HTTP/Playwright |

- `github_joblist` / `ats_board` 标记为「可信」来源，跳过严格正文校验；其余来源经 `job_validator` 过滤资讯/活动噪声，必要时由 DeepSeek 做结构化补全与打标签。
- 想接入更多在华外企：在 `ats_board.sources` 按 `平台 + board slug` 增配即可（`china_only: true` 会自动只保留中国岗位）。

---

## 数据与隐私

- 简历与会话以服务端内存 + 本地 `client_id` 记忆为主，**不上传至第三方除 LLM 提供商外的云服务**
- LLM 请求经 HTTPS 调用 DeepSeek 官方接口
- 仓库内示例简历与知识库均为虚构占位，请勿当作真实个人信息

---

## License

MIT — 见 [LICENSE](LICENSE)。
