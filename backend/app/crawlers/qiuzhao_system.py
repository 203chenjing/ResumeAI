"""27届秋招资讯聚合系统 Provider：直接读取秋招系统 SQLite 岗位库。

背景：
配套的「秋招」本地聚合系统已多源抓取并清洗了大量 27 届校招数据（搜狗微信 / 牛客 /
智联校招 / 前程无忧 / 实习僧 / 应届生求职网），存储在 data/qiuzhao.db 的 jobs 表。
ResumeAI 直接消费该库，可避免重复抓取、复用已沉淀的公司名/地点/薪资结构化字段。

合规：
- 仅读取本地已入库的公开数据，不新增网络请求；
- 被 crawl_sources.yml blocked_domains 命中的来源（如 51job/yingjiesheng）由
  merge 阶段统一过滤，本 provider 不绕过；
- 岗位保留原始 source_url 供用户跳转官方投递。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

from app.crawlers.base import CrawlerProvider, JobPosting
from app.config import settings

logger = logging.getLogger(__name__)

# 秋招系统数据库路径：默认取 backend/data/qiuzhao.db，
# 可用环境变量 QIUZHAO_DB_PATH 或 YAML 的 db_path 覆盖（不再写死开发机绝对路径）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = (
    Path(settings.qiuzhao_db_path)
    if settings.qiuzhao_db_path
    else _BACKEND_ROOT / "data" / "qiuzhao.db"
)

# 已知公司（用于公司名缺失时从标题/描述兜底提取）
KNOWN_COMPANIES = (
    # 互联网大厂
    "字节跳动", "腾讯", "阿里巴巴", "百度", "美团", "京东", "华为", "小米",
    "OPPO", "vivo", "网易", "快手", "拼多多", "滴滴", "蚂蚁集团",
    "携程", "哔哩哔哩", "商汤", "大疆", "比亚迪", "理想汽车", "蔚来", "小鹏",
    "地平线", "寒武纪", "联想", "中兴", "海康威视", "大华", "深信服", "奇安信",
    "360", "小红书", "得物", "货拉拉", "米哈游", "莉莉丝", "叠纸", "鹰角",
    "完美世界", "网易游戏", "三七互娱", "顺丰", "招商银行", "工商银行",
    "建设银行", "中国银行", "交通银行", "平安", "中国人寿", "万科",
    "保利", "中海", "龙湖", "宝洁", "联合利华", "欧莱雅", "京东方", "TCL",
    "格力", "美的", "海尔", "海信", "宁德时代", "中芯国际", "长江存储",
    "长鑫存储", "小马智行", "文远知行", "商汤科技", "旷视", "科大讯飞",
    # 国企/央企/金融机构
    "国家能源集团", "国家电网", "南方电网", "中国移动", "中国联通", "中国电信",
    "中国石油", "中国石化", "中国海油", "中国烟草", "光大证券", "中信证券",
    "国泰君安", "华泰证券", "招商证券", "德勤", "普华永道", "安永", "毕马威",
    # 半导体/芯片
    "德州仪器", "兆易创新", "北方华创", "中微公司", "拓荆科技",
    # 更多企业
    "中国航发", "帆软", "格科微", "绿盟科技", "中国银河证券", "中国华能",
    "禾赛科技", "招银网络科技", "汇川科技", "美敦力", "上汽集团", "养生堂",
    "农夫山泉", "万泰生物", "中国电子", "中国电科", "航天科技", "航天科工",
    "中国船舶", "CVTE", "淘天",
)

# 无效公司名（正则兜底时过滤）
INVALID_COMPANIES = frozenset(
    {
        "校园", "校招", "秋招", "春招", "招聘", "实习", "应届生", "求职",
        "面经", "笔试", "offer", "投递", "内推", "网申", "银行", "互联网",
        "科技公司", "集团", "公司", "名企", "推荐", "精选", "热门",
        "2027届", "27届", "2027", "毕业生", "应届", "暑期", "日常",
        "上海", "北京", "深圳", "杭州", "广州", "成都", "武汉", "南京",
        "西安", "苏州",
    }
)

# 讨论帖噪声：牛客/公众号讨论帖（选offer、求建议、开奖、面经交流）不是可投递岗位
DISCUSSION_NOISE = (
    "选offer", "选哪个", "求建议", "帮选", "求捞", "开奖", "求offer",
    "offer选择", "求内推码", "内推码发放", "面经分享", "面试经验",
    "笔试复盘", "oc", "offer比较", "怎么选", "要不要去", "求比较",
)

# 标题正则：XX公司校招/秋招/招聘
TITLE_COMPANY_RE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9·（）()&]{2,24}?)(?:校招|秋招|春招|招聘|实习)"
)


def _extract_company(title: str, description: str) -> str:
    """从标题/描述兜底提取公司名（TOP_COMPANIES 优先，正则兜底）。"""
    text = f"{title or ''} {description or ''}"
    for name in sorted(KNOWN_COMPANIES, key=len, reverse=True):
        if name in text:
            return name
    m = TITLE_COMPANY_RE.search(title or "")
    if m:
        name = m.group(1).strip().rstrip("【【")
        if name and name not in INVALID_COMPANIES and 2 <= len(name) <= 20:
            return name
    return ""


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return [str(t) for t in val if str(t).strip()][:8] if isinstance(val, list) else []
    except Exception:
        return []


def _split_locations(location: str) -> list[str]:
    """'上海·浦东新区' → ['上海', '浦东新区']；'北京' → ['北京']。"""
    if not location:
        return []
    parts = [p.strip() for p in re.split(r"[·、,/，|]", location) if p.strip()]
    return parts[:6]


def _stable_id(source: str, source_id: str) -> str:
    """稳定幂等 id：md5(source+source_id) 前 12 位。"""
    digest = hashlib.md5(f"{source}:{source_id}".encode("utf-8")).hexdigest()
    return digest[:12]


class QiuzhaoSystemProvider(CrawlerProvider):
    """从秋招系统 SQLite 岗位库直接导入 27 届校招岗位。"""

    name = "qiuzhao_system"

    async def fetch(
        self,
        config: dict | None = None,
        fetcher: object | None = None,
    ) -> list[JobPosting]:
        config = config or {}
        if not config.get("enabled", True):
            return []

        db_path = Path(config.get("db_path") or DEFAULT_DB_PATH)
        if not db_path.is_file():
            logger.warning("qiuzhao_system: 数据库不存在 %s", db_path)
            return []

        max_items = int(config.get("max_items", 3000))
        include_sources = config.get("sources") or None  # 如 ["sogou_wechat", "nowcoder"]

        jobs: list[JobPosting] = []
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            where = ""
            params: list = []
            if include_sources:
                placeholders = ",".join("?" * len(include_sources))
                where = f"WHERE source IN ({placeholders})"
                params = list(include_sources)
            rows = conn.execute(
                f"SELECT id, title, company, location, salary, education, job_type, "
                f"description, source, source_url, source_id, tags, publish_date, "
                f"deadline, created_at FROM jobs {where} ORDER BY id DESC LIMIT ?",
                params + [max_items * 2],  # 留出过滤余量
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.warning("qiuzhao_system: 读取数据库失败 %s: %s", db_path, e)
            return []

        for row in rows:
            try:
                title = (row["title"] or "").strip()
                if len(title) < 4:
                    continue
                if any(n in title for n in DISCUSSION_NOISE):
                    continue

                company = (row["company"] or "").strip()
                if not company:
                    company = _extract_company(title, row["description"] or "")
                if not company:
                    company = "招聘单位待确认"

                description = (row["description"] or "").strip()
                salary = (row["salary"] or "").strip()
                education = (row["education"] or "").strip()
                location = (row["location"] or "").strip()

                # JD 正文：描述优先，缺省时拼装基础字段，保证 validator 通过
                parts = [p for p in (description, salary, education) if p]
                if not parts:
                    parts = [title, company]
                jd_text = " ".join(parts)[:2000]

                tags = _parse_tags(row["tags"])
                channel = str(row["source"] or "qiuzhao")
                src_tags = [t for t in tags if t not in ("27届", "2027")][:4]
                job_tags = ["27届", "2027校招"] + src_tags

                published = (row["publish_date"] or "").strip()
                if not published:
                    published = (row["created_at"] or "")[:10]

                jobs.append(
                    JobPosting(
                        id=_stable_id(str(row["source"] or ""), str(row["source_id"] or "")),
                        company=company[:60],
                        role=title[:120],
                        source=self.name,
                        jd_text=jd_text,
                        jd_url=(row["source_url"] or "").strip(),
                        location=location,
                        deadline=(row["deadline"] or "").strip(),
                        channel=channel,
                        tags=job_tags,
                        locations=_split_locations(location),
                        job_type=str(row["job_type"] or ""),
                        published_at=published,
                        crawled_at=(row["created_at"] or "").strip(),
                        source_site=str(row["source"] or ""),
                        legitimacy="likely",
                    )
                )
                if len(jobs) >= max_items:
                    break
            except Exception as e:
                logger.debug("qiuzhao_system: 跳过单条 %s: %s", row["id"], e)

        logger.info("qiuzhao_system: 读取 %d 条岗位（%s）", len(jobs), db_path)
        return jobs
