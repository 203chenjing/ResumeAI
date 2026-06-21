---
name: resume-pdf-export
description: 将 Markdown 简历导出为 A4 单页 PDF。当用户要求导出 PDF、检查 PDF 排版、调整简历到一页、修复 PDF 格式问题时使用。
metadata:
  version: "1.0.0"
  author: ai-resume-optimizer
  tags: [pdf, resume, weasyprint, export]
---

# Resume PDF Export

## 适用范围

将 Markdown 格式的中文简历导出为符合 A4 单页规范的 PDF。本 Skill 是 [SKILL.md](../../SKILL.md) 中 PDF 导出环节的工具链说明。

## 工具脚本

| 脚本 | 路径 | 用途 |
| ---- | ---- | ---- |
| `markdown_resume_to_pdf.py` | `backend/tools/` | Markdown → PDF（A4 单页） |
| `check_resume_skill.py` | `backend/tools/` | Markdown 格式自检（分隔线/技能行/列表语法） |
| `crop_profile_photo.py` | `backend/tools/` | 个人照片裁剪到 540×790 px |

## 硬约束（违反即不合格）

1. PDF **必须严格 1 页**（不能 0、2、多页）
2. 页边距：上 2.0cm / 下 0.8cm / 左 2.0cm / 右 2.0cm
3. 字号：姓名 17pt / 章节标题 12.5pt / 学校&公司行 10.5pt / 正文 9.5pt
4. 行高 1.3，段后 2.5pt
5. 实习经历前、相关技能前各有一条可见水平线（`---`）
6. 章节标题无下划线
7. 有序列表（实习经历）无左缩进，编号与正文同起点
8. 相关技能恰好 4 条单行：工作技能 / 数据技能 / AI技能 / 语言能力
9. 不含「求职优势/求职摘要/个人总结」等总结块
10. 文件名：`公司+姓名+岗位.pdf`

## 工作流

### Step 1: 内容自检
人工 Review 简历内容（事实真实性、JD 匹配、量化指标），由 SKILL.md 主流程负责。

### Step 2: 格式预检（仅 Markdown）
```bash
python check_resume_skill.py input.md --markdown-only
```
输出 `Skill check: passed.` 才能继续；否则修复 Markdown。

### Step 3: 导出 PDF
```bash
python markdown_resume_to_pdf.py input.md
# 默认输出与输入同名的 .pdf
# 或指定 -o 路径：
python markdown_resume_to_pdf.py input.md -o "公司+姓名+岗位.pdf"
```

可选模式：
- `--mode standard`（默认）：干净最终版
- `--mode tight`：压缩段距（内容偏多时使用）
- `--mode diff`：保留 `<ins>`/`<del>` 标签渲染（修改痕迹版）

### Step 4: 验证
脚本自动调用 PyPDF2 检查页数，输出：
- `Page check: 1 page.` ✓
- `Skill check: passed.` ✓

任一失败 → 回到 Step 1 修复内容/格式。

## 常见故障与处理

| 现象 | 处理 |
| ---- | ---- |
| PDF 2 页 | 优先压缩内容（合并 bullet、缩短弱句、`相关技能` 强制 4 行），再用 `--mode tight` |
| PDF 0 页或导出报错 | 检查 Markdown 语法、图片路径、字体可用性 |
| 单页但底部空白 > 20mm | 补充真实 JD 相关内容（实习/技能），再 `--mode standard` |
| 照片遮挡文字 | 用 `crop_profile_photo.py` 裁剪，调整 `--padding-ratio` |

## 关键依赖

- WeasyPrint 62+（HTML/CSS → PDF 渲染引擎）
- markdown 3.7（Markdown 解析）
- PyPDF2 3.0（页数检查）
- Pillow 10+（照片处理）

Windows 安装 WeasyPrint 需要 GTK 库（已在 README 中说明）。

## 与 SKILL.md 的关系

SKILL.md（resume-tailor）负责**内容**：STAR 改写、JD 匹配、质量检查。
本 Skill 负责**格式**：Markdown → PDF 工具链与排版规范。两者协作完成完整改写流程。
