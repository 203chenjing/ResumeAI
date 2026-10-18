"""局部压缩 Prompt：只改指定 bullet，不重写全文。

刻意不做「整篇重写」：用户在改稿环节逐条确认过建议，整篇重写会把他的决策
一起冲掉，违背「人控 AI」。
"""
import json

SYSTEM = """你是中文简历的压缩编辑。任务：在**不改变事实**的前提下，把给定 bullet 改短。

必须遵守：
1. 数字、工具名、公司名、项目名、专有名词原样保留，一个都不能改
2. 保留编号与格式：`N. **小标题**：正文`（子要点是 `1）**小标题**：正文`）
3. 必删项：背景铺垫、动机解释、形容词堆砌、同义反复、流程套话
   - "为了提升用户体验，我们对…进行了优化" → "优化…"
   - "在项目中主要负责…相关工作" → "负责…"
   - "持续推动各方协同落地" → "推动落地"
4. 必留项：动作（做了什么）+ 方法（怎么做）+ 结果（数字）
5. 每条必须不超过 max_len，超出视为不合格
6. 不得合并或拆分 bullet，一条对一条

只输出 JSON：{"items": [{"id": 1, "text": "压缩后的整行文本"}]}"""


def build_compress_prompt(lines: list[dict], target_total: int, round_no: int = 1) -> tuple[str, str]:
    """lines: [{"id": 1, "text": "...", "max_len": 160}]"""
    payload = json.dumps(lines, ensure_ascii=False, indent=1)
    urgency = (
        "按 max_len 执行，正文部分比小标题更要压。"
        if round_no == 1
        else f"第 {round_no} 轮：上一轮压得不够，本轮必须删到 max_len 以内，只保留动作+方法+数字。"
    )
    user = f"""简历总字数需要压到约 {target_total} 字。逐条压缩下面 {len(lines)} 条 bullet：

{payload}

要求：
- 每条的 `max_len` 是**硬上限**（含编号与加粗），超出即不合格
- {urgency}
- 数字、工具名、专有名词原样保留
- items 的 id 必须与输入一一对应，text 输出完整一行（含编号）
"""
    return SYSTEM, user
