"""DeepSeek Tool Calls + 公开搜索：发现 27 届校招信息。"""
from __future__ import annotations

import json
import logging
import uuid

from app.config import settings
from app.crawlers.base import CrawlerProvider, JobPosting
from app.services.discovery_fallback import make_fallback_jobs_from_search_hits
from app.services.llm_client import client
from app.services.web_search import web_search

logger = logging.getLogger(__name__)

SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索 2027届/27届校招、提前批、实习的官方投递入口与资讯。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "中文搜索词，如「2027届校招 提前批 字节跳动 官方」",
                    }
                },
                "required": ["query"],
            },
        },
    }
]

DISCOVERY_SYSTEM = """你是 27 届校招信息发现助手。通过 web_search 工具检索公开网页，整理可投递岗位。
最终输出 JSON（无 markdown）：
{
  "jobs": [
    {
      "company": "公司名",
      "role": "批次或岗位名，含27届/2027届/提前批/实习",
      "jd_url": "官方投递链接",
      "jd_text": "一句话摘要",
      "job_type": "提前批|秋招|春招|实习|校招",
      "graduation_cohort": "27届"
    }
  ]
}
规则：
- 优先 27 届/2027 届；官方 campus 页即使未写届别也可保留
- jd_url 必须是 http(s) 官方校招/企业招聘页，禁止 BOSS/智联
- 最多 25 条，去重公司+批次"""


class SearchDiscoveryProvider(CrawlerProvider):
    name = "search_discovery"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: object | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        if not config.get("enabled", True):
            return []
        if not settings.deepseek_api_key:
            logger.info("search_discovery skipped: no DEEPSEEK_API_KEY")
            return []

        queries = list(config.get("queries") or [])
        if not queries:
            queries = [
                "2027届校招 提前批 互联网 官方投递",
                "27届秋招 大厂 校园招聘 2026",
                "2027届 暑期实习 官方 校招",
            ]
        max_queries = int(config.get("max_queries", 3))
        queries = queries[:max_queries]

        search_blob: list[dict] = []
        for q in queries:
            hits = await web_search(q, max_results=int(config.get("max_results_per_query", 6)))
            for h in hits:
                search_blob.append({**h, "query": q})

        if not search_blob:
            return []

        messages = [
            {"role": "system", "content": DISCOVERY_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"target_cohort": "27届", "search_results": search_blob[:18]},
                    ensure_ascii=False,
                ),
            },
        ]

        jobs: list[JobPosting] = []
        try:
            data = await client.chat_json(
                DISCOVERY_SYSTEM,
                json.dumps({"target_cohort": "27届", "search_results": search_blob[:18]}, ensure_ascii=False),
                max_tokens=4096,
                temperature=0.1,
            )
            raw_jobs = data.get("jobs") or []

            channel = config.get("channel", "AI搜索发现")
            for row in raw_jobs:
                company = str(row.get("company") or "").strip()
                role = str(row.get("role") or "").strip()
                jd_url = str(row.get("jd_url") or "").strip()
                if not company or not role or not jd_url.startswith("http"):
                    continue
                jobs.append(
                    JobPosting(
                        id=uuid.uuid4().hex[:12],
                        company=company[:60],
                        role=role[:120],
                        source=self.name,
                        jd_text=str(row.get("jd_text") or f"{company} {role}")[:500],
                        jd_url=jd_url,
                        channel=channel,
                        tags=["27届", "搜索发现", str(row.get("job_type") or "校招")],
                        job_type=str(row.get("job_type") or "校招")[:20],
                        legitimacy="likely",
                    )
                )
        except Exception:
            logger.exception("search_discovery LLM failed")

        if not jobs and search_blob:
            jobs = make_fallback_jobs_from_search_hits(
                search_blob,
                cohort="27届",
                source=self.name,
                channel=config.get("channel", "AI搜索发现"),
                max_jobs=int(config.get("max_jobs", 25)),
            )
            if jobs:
                logger.info("search_discovery fallback: %d jobs from search hits", len(jobs))

        logger.info("search_discovery: %d jobs from %d queries", len(jobs), len(queries))
        return jobs[: int(config.get("max_jobs", 25))]
