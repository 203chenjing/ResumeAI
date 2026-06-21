"""飞书多维表格 Provider：同步秋招岗位表。"""
from __future__ import annotations

import logging

from app.crawlers.base import CrawlerProvider, JobPosting
from app.services.feishu_bitable import FeishuBitableClient, FeishuBitableError, record_to_job

logger = logging.getLogger(__name__)


class FeishuBitableProvider(CrawlerProvider):
    name = "feishu_bitable"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: object | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        if not config.get("enabled", True):
            return []

        client = FeishuBitableClient.from_settings()
        if not client.is_configured():
            raise FeishuBitableError(
                "未配置飞书凭证：请在 backend/.env 设置 FEISHU_APP_ID + FEISHU_APP_SECRET，"
                "或 FEISHU_USER_ACCESS_TOKEN"
            )

        include_types = list(config.get("job_types_include") or ["秋招"])
        exclude_types = list(config.get("job_types_exclude") or ["实习", "春招", "暑期"])
        sources = list(config.get("sources") or [])
        jobs: list[JobPosting] = []

        for source in sources:
            if source.get("enabled") is False:
                continue
            sid = source.get("id", "")
            base_token = source.get("base_token", "")
            table_id = source.get("table_id", "")
            if not base_token or not table_id:
                logger.warning("feishu_bitable %s: missing base_token/table_id", sid)
                continue

            try:
                records = await client.list_records(
                    base_token,
                    table_id,
                    view_id=source.get("view_id", ""),
                )
                mapped = 0
                for record in records:
                    raw = record_to_job(
                        record,
                        source_id=sid,
                        channel=source.get("channel") or source.get("name") or "飞书秋招表",
                        tags=list(source.get("tags") or []),
                        field_map=source.get("field_map"),
                        include_types=include_types,
                        exclude_types=exclude_types,
                    )
                    if not raw:
                        continue
                    mapped += 1
                    jobs.append(
                        JobPosting(
                            id=raw["id"],
                            company=raw["company"],
                            role=raw["role"],
                            source=self.name,
                            jd_text=raw["jd_text"],
                            jd_url=raw.get("jd_url", ""),
                            location=raw.get("location", ""),
                            deadline=raw.get("deadline", ""),
                            channel=raw["channel"],
                            tags=raw.get("tags") or [],
                            city=raw.get("city", ""),
                            source_site=sid,
                            job_type=raw.get("job_type", "秋招"),
                            published_at=raw.get("published_at", ""),
                        )
                    )
                logger.info("feishu_bitable %s: %d/%d records kept (秋招)", sid, mapped, len(records))
            except FeishuBitableError:
                raise
            except Exception as e:
                logger.warning("feishu_bitable %s failed: %s", sid, e)

        return jobs
