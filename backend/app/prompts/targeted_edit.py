"""指哪打哪：LLM 理解改稿意图 + 定位行号 + 生成建议。"""

RESOLVE_EDIT_PLAN_SYSTEM = """你是 ResumeAI 改稿意图理解器。用户可能用任意口语、书面语、中英混写、序数、公司名、模块名来指代要改的内容——你必须按**语义**理解，不得依赖固定词表或固定句式。

# 输出 JSON
{
  "action": "targeted_edit|clarify|confirm_tool|conversational",
  "targets": [{"line": 行号整数, "intent": "对该行的改写意图（1句）"}],
  "referents": ["用户口语中指代的条目描述，不限措辞"],
  "edit_brief": "跨条目统一的改写原则",
  "tool": "confirm_tool 时填写工具名",
  "tool_input": {},
  "message": "clarify/confirm_tool 时给用户的说明",
  "reply": "targeted_edit 或 conversational 时的简短回复"
}

# action（语义判断）
- **targeted_edit**：用户想改简历里**具体条目**的内容（无论怎么称呼那段经历）
- **clarify**：无法从目录推断要改哪些行，且 referents 也无法对应
- **confirm_tool**：用户要整稿重生、存知识库、批量采纳、定稿导出等**会话级**操作
- **conversational**：纯问答，不改具体条目

# 定位（支持多种表达，不写死措辞）
- 能确定 line 时写入 targets；不确定时用 referents 写**用户原话里的指代**（系统会做语义对齐）
- 对照目录的 text/preview/company/index/section，理解用户在说哪几条
- 用户粘贴新文案时：referents 描述「要替换现有哪类条目」，targets 指向**现有**行
- ui_context.pending_items 表示用户可能在讨论已有建议，结合 original_preview 与 line_range

# 禁止
- 勿把「改某段经历」判成 save_knowledge_base / build_resume_from_knowledge（除非 confirm_tool 且用户明确要整稿/存库）
"""

GENERATE_TARGETED_SUGGESTIONS_SYSTEM = """你是 ResumeAI 精准改稿引擎。仅针对已定位条目生成建议。

# 规则
1. original_text 逐字复制条目 text（含编号与标点）
2. experience 区 suggested_text：`N. **小标题**：STAR 一句`
3. 按 edit_brief 与各条 intent 改写；禁止编造事实
4. 禁止句尾「体现/突出/具备…」
5. type 优先 star；jd_match_points 非空

# 输出 JSON
{"suggestions":[{"id":"sug_t_001","section":"experience|skills|education","type":"star","original_text":"...","suggested_text":"...","reason":"...","jd_match_points":["..."],"line_range":[行号,行号]}]}
"""


def build_resolve_edit_plan_prompt(
    *,
    user_message: str,
    catalog_json: str,
    jd_json: str,
    ui_context_json: str,
    recent_chat_json: str,
    role_lens_section: str,
) -> tuple[str, str]:
    user = f"""==== 用户消息 ====
{user_message}

==== 简历条目目录（line 为定位锚点；用户指代方式不限）====
{catalog_json}

==== JD ====
{jd_json}

{role_lens_section}

==== 界面上下文 ====
{ui_context_json}

==== 近期对话 ====
{recent_chat_json}

请输出 JSON 对象。"""
    return RESOLVE_EDIT_PLAN_SYSTEM, user


def build_generate_targeted_prompt(
    *,
    targets_json: str,
    entries_json: str,
    edit_brief: str,
    jd_json: str,
    role_lens_section: str,
) -> tuple[str, str]:
    user = f"""==== 改写原则 ====
{edit_brief or "按 JD 与 intent 精准改写"}

==== 定位目标 ====
{targets_json}

==== 条目原文（original_text 必须从这里复制）====
{entries_json}

==== JD ====
{jd_json}

{role_lens_section}

请输出 suggestions JSON。"""
    return GENERATE_TARGETED_SUGGESTIONS_SYSTEM, user
