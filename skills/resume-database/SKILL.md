---
name: resume-database
description: 简历知识库管理。维护经用户确认的经历素材（STAR、指标、项目事实），供改简历时抽取。对齐 ../../SKILL-resume-database.md。
metadata:
  version: "1.0.0"
  parent_skill: "../../SKILL-resume-database.md"
---

# Resume Database（简历知识库）

## 在 Demo 中的用法

1. 上传页 **「简历知识库」** 区域填写或粘贴素材
2. **个人照片（自定义模块）**：上传后会裁剪并写入简历 Markdown，导出 PDF 时显示
3. 点击「保存知识库」写入当前会话
4. 生成修改建议时，AI 会读取知识库补充 STAR 与指标，**避免为凑 JD 而编造**
5. 知识库比投递简历更完整；一页 PDF 简历是知识库的压缩版

## 个人照片 API

| 接口 | 说明 |
|------|------|
| `POST /api/knowledge-base/photo` | multipart: session_id + file |
| `GET /api/knowledge-base/photo/{session_id}` | 预览/下载 |
| `DELETE /api/knowledge-base/photo/{session_id}` | 移除 |

## 应写什么

- 各段实习的 STAR（背景/任务/行动/结果）
- 可量化指标及来源（或 `[待确认]`）
- 并列项目层级（如同一公司下多条工作线）
- JD 无关但真实的备用素材

## 不应写什么

- 投递版排版（四行技能、`---` 分隔线等）
- 未确认的数字、公司、项目
- 整段复制 JD

## API

| 接口 | 说明 |
|------|------|
| `GET /api/knowledge-base/template` | 空白模板 |
| `GET /api/knowledge-base/{session_id}` | 读取会话知识库 |
| `PUT /api/knowledge-base` | 保存 `{ session_id, content }` |

## 与主 SKILL 关系

- [SKILL.md](../../SKILL.md)（resume-tailor）：一页投递版改写与 PDF 规范
- [SKILL-resume-database.md](../../SKILL-resume-database.md)：知识库完整规范
- 本文件：Demo 内嵌入口说明
