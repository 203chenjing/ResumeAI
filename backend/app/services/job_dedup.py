"""岗位去重：URL 规范化 + 公司/岗位指纹。"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, urlparse, urlunparse

_STRIP_SUFFIX = re.compile(r"(有限公司|股份有限公司|集团|科技|网络)$")


def normalize_company(name: str) -> str:
    s = " ".join((name or "").split()).strip().lower()
    s = re.sub(r"[\s（）()·\-—]", "", s)
    prev = None
    while s != prev:
        prev = s
        s = _STRIP_SUFFIX.sub("", s)
    return s[:40]


def normalize_role(role: str) -> str:
    s = " ".join((role or "").split()).strip().lower()
    s = re.sub(r"[【】\[\]|｜]", " ", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"\d{2}\.\d{2}收录", "", s)
    s = re.sub(r"立即投递|官网投递|地点[：:].*", "", s)
    return s[:80].strip()


def canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
        if not p.scheme:
            return url.strip().lower()
        host = p.netloc.lower()
        path = p.path.rstrip("/") or "/"
        # 微信文章保留 path，去掉 tracking query
        if "mp.weixin.qq.com" in host:
            return f"{p.scheme}://{host}{path}".lower()
        # 字节/牛客详情页保留 path
        if any(x in host for x in ("nowcoder.com", "bytedance.com", "yingjiesheng.com")):
            q = parse_qs(p.query)
            # 保留关键 id 参数
            keep = []
            for k in ("id", "companyId", "positionId"):
                if k in q:
                    keep.append(f"{k}={q[k][0]}")
            qs = "?" + "&".join(keep) if keep else ""
            return f"{p.scheme}://{host}{path}{qs}".lower()
        return f"{p.scheme}://{host}{path}".lower()
    except Exception:
        return url.strip().lower()


def fingerprint(job: dict) -> str:
    """生成去重指纹：优先详情页 URL，否则公司+岗位+来源地。"""
    url = canonical_url(job.get("jd_url", ""))
    # 列表页 URL 不能作为唯一键（多岗位同页）
    is_list_page = any(
        x in url
        for x in (
            "/schedule",
            "/recruitmentfairlist",
            "/recruitmentinfolist",
            "/anony/xxfb",
            "ncss.cn/",
            "bjbys.net.cn/",
            "campus/position$",
        )
    ) and "/detail" not in url and "/job-" not in url and "/job_" not in url

    if url and not is_list_page:
        return f"url:{url}"

    company = normalize_company(job.get("company", ""))
    role = normalize_role(job.get("role", ""))
    city = (job.get("city") or "").strip()
    locs = ",".join(sorted(job.get("locations") or [])[:3])
    raw = f"{company}|{role}|{city}|{locs}|{job.get('source_site', '')}"
    return "fp:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def is_duplicate(job: dict, seen: set[str]) -> bool:
    fp = fingerprint(job)
    if fp in seen:
        return True
    # 次级：同公司+同 role 前缀（无 URL 的聚合条目）
    company = normalize_company(job.get("company", ""))
    role = normalize_role(job.get("role", ""))[:40]
    if company and role:
        soft = f"soft:{company}|{role}"
        if soft in seen:
            return True
    return False


def register_fingerprint(job: dict, seen: set[str]) -> None:
    seen.add(fingerprint(job))
    company = normalize_company(job.get("company", ""))
    role = normalize_role(job.get("role", ""))[:40]
    if company and role:
        seen.add(f"soft:{company}|{role}")


def deduplicate_jobs(jobs: list[dict], *, keep: str = "first") -> tuple[list[dict], dict]:
    """
    对列表去重。keep=first 保留先出现的（通常较新）。
    返回 (去重后列表, stats)
    """
    seen: set[str] = set()
    out: list[dict] = []
    dup = 0
    for job in jobs:
        if is_duplicate(job, seen):
            dup += 1
            continue
        register_fingerprint(job, seen)
        out.append(job)
    return out, {"total_in": len(jobs), "unique": len(out), "duplicates_removed": dup}
