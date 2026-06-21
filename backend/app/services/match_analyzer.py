"""匹配度分析服务。"""
import json
import logging

from app.models.schemas import JDAnalysis, MatchResult
from app.prompts.match_analysis import build_match_prompt
from app.services.llm_client import client

logger = logging.getLogger(__name__)


async def analyze_match(resume_md: str, jd: JDAnalysis) -> MatchResult:
    system, user = build_match_prompt(resume_md, json.dumps(jd.model_dump(), ensure_ascii=False, indent=2))
    data = await client.chat_json(system, user, temperature=0.2)
    return MatchResult(**data)
