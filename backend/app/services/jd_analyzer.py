"""JD 分析服务。"""
import logging

from app.models.schemas import JDAnalysis
from app.prompts.jd_analysis import build_jd_analysis_prompt
from app.services.llm_client import client

logger = logging.getLogger(__name__)


async def analyze_jd(jd_text: str) -> JDAnalysis:
    if not jd_text or len(jd_text.strip()) < 30:
        raise ValueError("JD 内容过短")
    system, user = build_jd_analysis_prompt(jd_text)
    data = await client.chat_json(system, user, temperature=0.2)
    return JDAnalysis(**data)
