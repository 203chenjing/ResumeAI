"""简历解析服务：原始文本 → ParsedResume + Markdown。"""
import json
import logging

from app.models.schemas import ParsedResume
from app.prompts.parse_resume import build_parse_prompt
from app.services.llm_client import client
from app.services.md_builder import build_resume_markdown

logger = logging.getLogger(__name__)


async def parse_resume_text(raw_text: str) -> tuple[ParsedResume, str]:
    """解析简历原始文本，返回 (ParsedResume, Markdown)。"""
    if not raw_text or len(raw_text.strip()) < 30:
        raise ValueError("简历内容过短或为空，请检查文件")

    system, user = build_parse_prompt(raw_text)
    data = await client.chat_json(system, user, temperature=0.1)
    try:
        parsed = ParsedResume(**data)
    except Exception as e:
        logger.error(f"ParsedResume validation failed: {e}, data={json.dumps(data)[:300]}")
        raise ValueError(f"简历解析结果格式异常: {e}") from e

    parsed.raw_markdown = build_resume_markdown(parsed)
    return parsed, parsed.raw_markdown
