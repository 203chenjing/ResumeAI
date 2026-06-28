"""爬虫 Provider 抽象：对标 JobSpy + career-ops scan providers。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobPosting:
    id: str
    company: str
    role: str
    source: str
    jd_text: str
    jd_url: str = ""
    location: str = ""
    deadline: str = ""
    channel: str = ""
    tags: list[str] = field(default_factory=list)
    crawled_at: str = ""
    city: str = ""  # 配置来源地（YAML city）
    source_site: str = ""  # crawl_sources 中的 source id
    locations: list[str] = field(default_factory=list)  # 从 JD 解析的工作地
    job_type: str = ""
    published_at: str = ""
    validation_status: str = "pending"
    validation_issues: list[str] = field(default_factory=list)
    referral_code: str = ""  # 内推码（GitHub 仓库等来源自带）
    legitimacy: str = ""  # 真实性分级：trusted | likely | suspect

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("crawled_at"):
            d["crawled_at"] = datetime.now().isoformat()
        return d


class CrawlerProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(
        self,
        config: dict | None = None,
        fetcher: object | None = None,
    ) -> list[JobPosting]:
        ...

    def normalize(self, raw: dict) -> JobPosting:
        return JobPosting(
            id=raw.get("id", ""),
            company=raw.get("company", ""),
            role=raw.get("role", ""),
            source=self.name,
            jd_text=raw.get("jd_text", ""),
            jd_url=raw.get("jd_url", ""),
            location=raw.get("location", ""),
            deadline=raw.get("deadline", ""),
            channel=raw.get("channel", self.name),
            tags=raw.get("tags") or [],
        )
