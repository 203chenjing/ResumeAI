"""飞书多维表格 → 岗位 Feed 映射（支持仅导入秋招）。"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FEISHU_API = "https://open.feishu.cn/open-apis"

DEFAULT_FIELD_ALIASES: dict[str, list[str]] = {
    "company": ["公司名称", "公司", "企业名称", "公司名", "企业"],
    "role": ["招聘岗位", "岗位", "职位", "职位名称", "招聘岗位名称", "校招岗位"],
    "job_type": ["招聘类型", "类型", "批次", "招聘批次", "项目"],
    "location": ["工作地点", "城市", "地点", "工作城市", "base"],
    "deadline": ["截止时间", "网申截止", "投递截止", "截止日期", "截止"],
    "jd_url": ["投递链接", "网申链接", "官网链接", "链接", "投递地址", "网申地址"],
    "published_at": ["更新时间", "收录时间", "发布日期", "日期", "收录"],
    "industry": ["行业", "公司行业", "所属行业"],
    "notes": ["备注", "说明", "内推码", "其他"],
}

EXCLUDE_TYPE_KEYWORDS = ("实习", "春招", "暑期", "日常实习", "寒假实习")
INCLUDE_TYPE_KEYWORDS = ("秋招",)


class FeishuBitableError(RuntimeError):
    pass


def _clean_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def extract_cell_text(value: Any) -> str:
    """将飞书单元格值展平为可读字符串。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        if value > 1_000_000_000_000:
            try:
                return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
            except (OSError, OverflowError, ValueError):
                return str(value)
        return str(value)
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            t = extract_cell_text(item)
            if t:
                parts.append(t)
        return _clean_text(" ".join(parts))
    if isinstance(value, dict):
        if "link" in value or "text" in value:
            link = _clean_text(str(value.get("link") or ""))
            text = _clean_text(str(value.get("text") or ""))
            if link and text and link != text:
                return f"{text} {link}"
            return link or text
        if "name" in value:
            return _clean_text(str(value.get("name") or ""))
        if "value" in value:
            return extract_cell_text(value.get("value"))
    return _clean_text(str(value))


def resolve_field_map(
    record_fields: dict[str, Any],
    configured: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """按别名从一行记录中解析标准字段。"""
    aliases = {**DEFAULT_FIELD_ALIASES, **(configured or {})}
    actual_names = list(record_fields.keys())
    resolved: dict[str, str] = {}

    for key, candidates in aliases.items():
        for name in candidates:
            if name in record_fields:
                resolved[key] = extract_cell_text(record_fields[name])
                break
        if key not in resolved:
            for actual in actual_names:
                if any(c in actual for c in candidates):
                    resolved[key] = extract_cell_text(record_fields[actual])
                    break
    return resolved


def infer_job_type(*parts: str) -> str:
    text = " ".join(p for p in parts if p)
    for keyword, label in (
        ("秋招", "秋招"),
        ("提前批", "提前批"),
        ("补录", "补录"),
        ("春招", "春招"),
        ("实习", "实习"),
        ("校招", "校招"),
        ("社招", "社招"),
    ):
        if keyword in text:
            return label
    return "校招"


def matches_job_type_filter(
    mapped: dict[str, str],
    *,
    include_types: list[str] | None = None,
    exclude_types: list[str] | None = None,
) -> bool:
    """判断是否属于目标招聘类型（默认仅秋招）。"""
    include_types = include_types or list(INCLUDE_TYPE_KEYWORDS)
    exclude_types = exclude_types or list(EXCLUDE_TYPE_KEYWORDS)

    blob = " ".join(
        [
            mapped.get("job_type", ""),
            mapped.get("role", ""),
            mapped.get("company", ""),
            mapped.get("notes", ""),
        ]
    )
    if not blob.strip():
        return False

    if any(k in blob for k in exclude_types) and not any(k in blob for k in include_types):
        return False

    if include_types:
        return any(k in blob for k in include_types)
    return True


def record_to_job(
    record: dict[str, Any],
    *,
    source_id: str,
    channel: str,
    tags: list[str] | None = None,
    field_map: dict[str, list[str]] | None = None,
    include_types: list[str] | None = None,
    exclude_types: list[str] | None = None,
) -> dict[str, Any] | None:
    fields = record.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        return None

    mapped = resolve_field_map(fields, field_map)
    if not matches_job_type_filter(mapped, include_types=include_types, exclude_types=exclude_types):
        return None

    company = mapped.get("company", "")
    role = mapped.get("role", "")
    if not company and not role:
        title = extract_cell_text(fields.get("标题") or fields.get("名称") or "")
        if title:
            parts = re.split(r"[\s|｜/]+", title, maxsplit=1)
            company = parts[0]
            role = parts[1] if len(parts) > 1 else title
    if not company or not role:
        return None

    jd_url = mapped.get("jd_url", "")
    if jd_url and not jd_url.startswith("http"):
        m = re.search(r"https?://\S+", jd_url)
        if m:
            jd_url = m.group(0).rstrip(".,;)")
        else:
            jd_url = ""

    location = mapped.get("location", "")
    deadline = mapped.get("deadline", "")
    published_at = mapped.get("published_at", "")
    industry = mapped.get("industry", "")
    notes = mapped.get("notes", "")

    job_type = mapped.get("job_type") or infer_job_type(role, notes)
    if job_type not in include_types and include_types:
        job_type = infer_job_type(job_type, role, notes)

    jd_parts = [f"公司：{company}", f"岗位：{role}"]
    if location:
        jd_parts.append(f"地点：{location}")
    if deadline:
        jd_parts.append(f"截止：{deadline}")
    if industry:
        jd_parts.append(f"行业：{industry}")
    if notes:
        jd_parts.append(f"备注：{notes}")
    if jd_url:
        jd_parts.append(f"投递：{jd_url}")

    record_id = record.get("record_id") or ""
    stable = record_id or hashlib.md5(f"{company}|{role}|{jd_url}".encode()).hexdigest()[:12]

    out_tags = list(tags or [])
    out_tags.append("秋招")
    if industry:
        out_tags.append(f"行业:{industry}")
    if location:
        for city in re.split(r"[/、,，\s]+", location):
            c = city.strip()
            if c and len(c) <= 6:
                out_tags.append(f"工作地:{c}")

    return {
        "id": f"feishu_{stable}",
        "company": company,
        "role": role,
        "source": "feishu_bitable",
        "jd_text": "\n".join(jd_parts),
        "jd_url": jd_url,
        "location": location,
        "deadline": deadline,
        "channel": channel,
        "tags": out_tags,
        "city": location,
        "source_site": source_id,
        "job_type": job_type if job_type in (include_types or [job_type]) else (include_types or ["秋招"])[0],
        "published_at": published_at,
        "crawled_at": datetime.now().isoformat(),
    }


class FeishuBitableClient:
    def __init__(
        self,
        *,
        app_id: str = "",
        app_secret: str = "",
        user_access_token: str = "",
        base_url: str = FEISHU_API,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token
        self.base_url = base_url.rstrip("/")
        self._tenant_token = ""
        self._tenant_token_expires = 0.0

    @classmethod
    def from_settings(cls) -> "FeishuBitableClient":
        return cls(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            user_access_token=settings.feishu_user_access_token,
            base_url=settings.feishu_api_base,
        )

    def is_configured(self) -> bool:
        return bool(self.user_access_token or (self.app_id and self.app_secret))

    async def _get_tenant_token(self, client: httpx.AsyncClient) -> str:
        if self.user_access_token:
            return self.user_access_token

        now = datetime.now().timestamp()
        if self._tenant_token and now < self._tenant_token_expires - 60:
            return self._tenant_token

        resp = await client.post(
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuBitableError(data.get("msg") or "获取 tenant_access_token 失败")
        self._tenant_token = data.get("tenant_access_token") or ""
        self._tenant_token_expires = now + int(data.get("expire") or 7200)
        return self._tenant_token

    async def _auth_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        token = await self._get_tenant_token(client)
        return {"Authorization": f"Bearer {token}"}

    async def list_fields(self, base_token: str, table_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._auth_headers(client)
            items: list[dict[str, Any]] = []
            page_token = ""
            while True:
                params: dict[str, Any] = {"page_size": 100}
                if page_token:
                    params["page_token"] = page_token
                resp = await client.get(
                    f"{self.base_url}/bitable/v1/apps/{base_token}/tables/{table_id}/fields",
                    headers=headers,
                    params=params,
                )
                data = resp.json()
                if data.get("code") != 0:
                    raise FeishuBitableError(data.get("msg") or "读取字段失败")
                body = data.get("data") or {}
                items.extend(body.get("items") or [])
                if not body.get("has_more"):
                    break
                page_token = body.get("page_token") or ""
            return items

    async def list_records(
        self,
        base_token: str,
        table_id: str,
        *,
        view_id: str = "",
        page_size: int = 500,
        filter_body: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = await self._auth_headers(client)
            items: list[dict[str, Any]] = []
            page_token = ""
            while True:
                payload: dict[str, Any] = {}
                if view_id:
                    payload["view_id"] = view_id
                if filter_body:
                    payload["filter"] = filter_body

                params: dict[str, Any] = {"page_size": min(page_size, 500)}
                if page_token:
                    params["page_token"] = page_token

                resp = await client.post(
                    f"{self.base_url}/bitable/v1/apps/{base_token}/tables/{table_id}/records/search",
                    headers=headers,
                    params=params,
                    json=payload,
                )
                data = resp.json()
                if data.get("code") != 0:
                    raise FeishuBitableError(data.get("msg") or "读取记录失败")
                body = data.get("data") or {}
                items.extend(body.get("items") or [])
                if not body.get("has_more"):
                    break
                page_token = body.get("page_token") or ""
            return items
