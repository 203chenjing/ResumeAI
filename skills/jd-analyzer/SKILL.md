---
name: jd-analyzer
description: 解析岗位 JD 文本，提取结构化需求清单（核心/加分项/关键词/软技能/行业术语），并对 JD 真实性做基础判别。当用户粘贴 JD、需要分析岗位要求、识别假招聘时使用。
metadata:
  version: "1.0.0"
  author: ai-resume-optimizer
  tags: [jd, recruitment, ai-product, scam-detection]
---

# JD Analyzer

## 适用范围

从中文岗位 JD（Job Description）原文中提取结构化字段，作为后续简历修改和匹配度评分的输入。

## 输入

- JD 文本（粘贴原文，建议 ≥ 100 字）
- 可选：JD 来源 URL

## 输出（JSON）

```json
{
  "role": "岗位名称",
  "company": "公司名称",
  "archetype": "AI产品经理 | 数据分析 | 前端开发 | 后端开发 | 算法工程师 | 运营 | UI设计 | 项目管理 | 销售 | HR | 职能 | 其他",
  "core_requirements": ["JD 写明的硬性条件"],
  "preferred_requirements": ["JD 中的加分项"],
  "keywords": ["技术词/工具名/产品名"],
  "soft_skills": ["沟通/协作/思维等软实力"],
  "industry_terms": ["行业专有名词"],
  "legitimacy_score": 0-100,
  "legitimacy_flags": ["可疑信号"],
  "ranking": {
    "核心匹配": [],
    "可强化匹配": [],
    "不相关/弱相关": []
  }
}
```

## 真实性判别规则（legitimacy_score）

默认 100，按以下规则减分：

| 信号 | 减分 |
| ---- | ---- |
| 无具体公司名 / 公司名仅为「某公司」「保密」 | -15 |
| 薪资明显高于行业（初级岗月薪 5w+） | -20 |
| 仅用个人邮箱（@qq/@163/@gmail）无企业邮箱 | -10 |
| 要求支付费用、押金、培训费 | -60（强诈骗） |
| 工作地点模糊（仅写「全国」「线上」无具体城市） | -5 |
| JD 极短（< 100 字）或大量营销 emoji | -10 |
| 含「日结」「轻松月入」「在家兼职」 | -30 |

`legitimacy_score < 60` 视为高风险，前端应展示警示提示。

## 工作流

### Step 1: 输入校验
- JD 长度 < 50 字 → 返回错误「内容过短」
- JD 长度 > 50 字 → 进入分析

### Step 2: LLM 调用
- 模型：DeepSeek (`deepseek-chat`)
- response_format: `{"type": "json_object"}`
- temperature: 0.2（保证一致性）

### Step 3: 后处理
- 字段缺失补默认值
- archetype 限制在白名单内
- legitimacy_score 范围 0-100

## 与简历改写的协作

JD 分析输出的 `archetype` 用于简历改写时选择「强化哪些经历」：
- AI 产品经理 → 强化 RAG/LLM/多模态/Agent 等经历
- 数据分析 → 强化 SQL/Python/AB 实验/指标体系经历
- 前端开发 → 强化 React/Vue/性能优化/组件库经历

`keywords` 列表用于关键词嵌入检查（`keyword` 类型的修改建议必须命中至少 1 个）。
