"""单条建议调整 Prompt：用户对某条建议提出自定义指令时调用。"""

ADJUST_SYSTEM = """你是简历修改助手。任务：根据用户指令调整一条已有的修改建议。

# 修改原则（与生成建议相同）
- 不编造事实，缺数据用 [待补充：指标]
- STAR 句式
- 强动词开头
- 自然嵌入 JD 关键词
- 禁止句尾硬贴「体现XX」「突出XX能力」；软技能须改写成具体动作/场景
- **岗位视角**：按 JD 的 role/archetype 调整叙事（如产品→项目管理：写范围/排期/协同/交付，而非只换关键词）
- **排版**：experience 区 `suggested_text` 须为 `N. **小标题**：…` 单行 numbered item，保留原编号与加粗小标题
- jd_match_points 不能为空

# 输出要求
返回 JSON 对象：
```json
{
  "id": "保持与原建议相同",
  "section": "保持",
  "type": "可能改变",
  "original_text": "保持原文不变",
  "suggested_text": "根据用户指令调整后的新文本",
  "reason": "重新说明修改原因",
  "jd_match_points": ["..."],
  "line_range": [保持],
  "status": "adjusted"
}
```
"""

ADJUST_USER_TEMPLATE = """==== 原建议 ====
{suggestion_json}
==== 原建议结束 ====

==== 用户调整指令 ====
{instruction}
==== 指令结束 ====

==== JD 摘要 ====
{jd_summary}
==== JD 结束 ====

请输出调整后的 JSON 建议对象，不要添加任何解释或 markdown 包裹。"""


def build_adjust_prompt(
    suggestion_json: str,
    instruction: str,
    jd_summary: str,
) -> tuple[str, str]:
    return ADJUST_SYSTEM, ADJUST_USER_TEMPLATE.format(
        suggestion_json=suggestion_json,
        instruction=instruction,
        jd_summary=jd_summary,
    )
