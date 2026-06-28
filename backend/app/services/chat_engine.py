"""聊天引擎：流式生成回复 + 解析新建议。"""
import json
import logging
import re
import uuid
from typing import AsyncGenerator

from app.models.schemas import ChatMessage, JDAnalysis, Suggestion
from app.prompts.chat_system import build_chat_messages
from app.services.llm_client import client
from app.services.suggestion_engine import (
    _filter_noop_suggestions,
    _filter_stiff_keyword_suggestions,
    _normalize_experience_suggestions,
)
from app.services.suggestion_anchor import anchor_suggestions

logger = logging.getLogger(__name__)

CHAT_REPLY_RE = re.compile(r"\[CHAT_REPLY\](.*?)\[/CHAT_REPLY\]", re.DOTALL)
NEW_SUG_RE = re.compile(r"\[NEW_SUGGESTIONS\](.*?)\[/NEW_SUGGESTIONS\]", re.DOTALL)


def _parse_suggestions_json(block: str) -> list[dict]:
    """从 NEW_SUGGESTIONS 区块提取 JSON 数组（容忍模型在数组前插入说明文字）。"""
    text = block.strip()
    if not text:
        return []

    # 去掉 markdown 代码块
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 避免误匹配说明文字里的 "[]"
    obj_array = re.search(r"\[\s*\{", text)
    if obj_array:
        start = obj_array.start()
    elif "[]" in text:
        return []
    else:
        start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.warning("No JSON array found in NEW_SUGGESTIONS block: %s", text[:200])
        return []

    json_text = text[start : end + 1]
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.warning("JSON decode failed: %s, text=%s", e, json_text[:300])
        return []

    if not isinstance(data, list):
        logger.warning("NEW_SUGGESTIONS is not a list: %s", type(data))
        return []
    return [item for item in data if isinstance(item, dict)]


async def stream_chat(
    user_message: str,
    chat_history: list[ChatMessage],
    current_resume: str,
    current_suggestions: list[Suggestion],
    jd: JDAnalysis,
    photo_context: str = "",
    ui_context: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """流式聊天：逐 token 推送 + 最终解析新建议。"""
    history_dicts = [m.model_dump() for m in chat_history]
    messages = build_chat_messages(
        chat_history=history_dicts,
        user_message=user_message,
        current_resume=current_resume,
        current_suggestions_json=json.dumps(
            [s.model_dump() for s in current_suggestions], ensure_ascii=False
        ),
        jd_analysis_json=json.dumps(jd.model_dump(), ensure_ascii=False),
        photo_context=photo_context,
        ui_context_json=json.dumps(ui_context or {}, ensure_ascii=False),
    )

    full_text = ""
    chat_reply_emitted = False
    in_chat_section = False

    async for chunk in client.chat_stream(messages, temperature=0.5, max_tokens=3000):
        full_text += chunk
        if chat_reply_emitted:
            continue
        # 一旦检测到 [CHAT_REPLY] 段，按字符流式输出回复部分
        if "[CHAT_REPLY]" in full_text and not in_chat_section:
            in_chat_section = True
            after = full_text.split("[CHAT_REPLY]", 1)[1]
            if after:
                yield {"type": "text", "content": after}
        elif in_chat_section and "[/CHAT_REPLY]" not in full_text:
            yield {"type": "text", "content": chunk}
        elif in_chat_section and "[/CHAT_REPLY]" in full_text and not chat_reply_emitted:
            # 输出最后一段
            tail = full_text.split("[/CHAT_REPLY]", 1)[0].split("[CHAT_REPLY]", 1)[1]
            chat_reply_emitted = True
            in_chat_section = False
            # 终结 reply 段
            yield {"type": "reply_end"}

    # 解析 new_suggestions
    reply_match = CHAT_REPLY_RE.search(full_text)
    new_sug_match = NEW_SUG_RE.search(full_text)
    reply_text = reply_match.group(1).strip() if reply_match else full_text.strip()

    new_suggestions: list[Suggestion] = []
    if new_sug_match:
        arr = _parse_suggestions_json(new_sug_match.group(1))
        for item in arr:
            if not item.get("id"):
                item["id"] = f"sug_chat_{uuid.uuid4().hex[:8]}"
            item.setdefault("status", "pending")
            item.setdefault("line_range", [0, 0])
            item.setdefault("jd_match_points", [])
            try:
                new_suggestions.append(Suggestion(**item))
            except Exception as e:
                logger.warning("Skip invalid chat suggestion: %s, item=%s", e, item)

    # 容错：模型漏写闭合标签或未包在 NEW_SUGGESTIONS 内时，尝试从尾部解析 JSON
    if not new_suggestions:
        tail = ""
        if "[/CHAT_REPLY]" in full_text:
            tail = full_text.split("[/CHAT_REPLY]", 1)[1]
        elif "[NEW_SUGGESTIONS]" in full_text:
            tail = full_text.split("[NEW_SUGGESTIONS]", 1)[1]
        if tail.strip():
            arr = _parse_suggestions_json(tail)
            for item in arr:
                if not item.get("id"):
                    item["id"] = f"sug_chat_{uuid.uuid4().hex[:8]}"
                item.setdefault("status", "pending")
                item.setdefault("line_range", [0, 0])
                item.setdefault("jd_match_points", [])
                try:
                    new_suggestions.append(Suggestion(**item))
                except Exception as e:
                    logger.warning("Skip fallback chat suggestion: %s, item=%s", e, item)
            if new_suggestions:
                logger.info("Recovered %d suggestions via fallback parse", len(new_suggestions))

    before_filter = len(new_suggestions)
    new_suggestions = _filter_noop_suggestions(new_suggestions)
    new_suggestions = _filter_stiff_keyword_suggestions(new_suggestions)
    new_suggestions = _normalize_experience_suggestions(new_suggestions)
    new_suggestions = anchor_suggestions(new_suggestions, current_resume)
    if len(new_suggestions) < before_filter:
        logger.info("Dropped %d invalid chat suggestions", before_filter - len(new_suggestions))

    if not new_suggestions and new_sug_match and reply_text:
        # 模型声明有建议块但解析/过滤后为空：统一诚实回复（不依赖固定话术正则）
        block = new_sug_match.group(1).strip()
        if block and block != "[]":
            reply_text = "我没有成功生成可处理的新建议，请再说明要改目录中的哪几条、希望改成什么样。"
        elif "[]" in block:
            reply_text = reply_text or "本次没有生成新建议；如需改具体条目，请直接说想改哪一段经历。"

    yield {
        "type": "done",
        "reply_text": reply_text,
        "new_suggestions": [s.model_dump() for s in new_suggestions],
    }
