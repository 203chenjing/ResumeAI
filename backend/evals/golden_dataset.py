"""选岗 Copilot 评测黄金集：固定岗位数据 + 期望工具路由。

设计原则：
- 数据固定（FIXTURE_JOBS / FIXTURE_RESUME），评测只考察「真实 DeepSeek 会不会为某类问题
  调用正确的工具」，与线上数据无关、可复现。
- expected_tools 只列「必须命中」的工具名；模型多调一两个无害工具不算错（ToolCorrectness
  默认非严格匹配，按命中率打分）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

FIXTURE_JOBS: list[dict] = [
    {
        "id": "j1",
        "company": "字节跳动",
        "role": "后端开发实习生",
        "job_type": "实习",
        "location": "北京",
        "locations": ["北京"],
        "jd_url": "https://jobs.bytedance.com/1",
        "jd_text": "Golang/Python 后端 微服务 分布式 实习 北京",
        "source": "github_joblist",
        "referral_code": "AB12CD",
        "validation_status": "ok",
    },
    {
        "id": "j2",
        "company": "腾讯",
        "role": "前端开发工程师",
        "job_type": "校招",
        "location": "深圳",
        "locations": ["深圳"],
        "jd_url": "https://careers.tencent.com/2",
        "jd_text": "React TypeScript 前端 校招 深圳",
        "source": "github_joblist",
        "validation_status": "ok",
    },
    {
        "id": "j3",
        "company": "阿里巴巴",
        "role": "数据开发工程师",
        "job_type": "校招",
        "location": "杭州",
        "locations": ["杭州"],
        "jd_url": "https://talent.alibaba.com/3",
        "jd_text": "Spark Flink 数据仓库 校招 杭州",
        "source": "ats_board",
        "validation_status": "ok",
    },
    {
        "id": "j4",
        "company": "美团",
        "role": "后端开发工程师",
        "job_type": "校招",
        "location": "北京",
        "locations": ["北京"],
        "jd_url": "https://campus.meituan.com/4",
        "jd_text": "Java 后端 高并发 校招 北京",
        "source": "github_joblist",
        "validation_status": "ok",
    },
]

FIXTURE_RESUME = (
    "# 简历\n后端开发方向，熟悉 Python / Golang、微服务、分布式系统，"
    "有高并发后端项目经验，目标城市北京。"
)

FIXTURE_PREFS = {
    "target_roles": ["后端开发"],
    "target_cities": ["北京"],
    "job_types": ["实习", "校招"],
    "company_wishlist": [],
    "company_blocklist": [],
    "extra_notes": "",
}


@dataclass
class Golden:
    id: str
    input: str
    expected_tools: list[str]
    expected_block_types: list[str] = field(default_factory=list)
    comment: str = ""


GOLDENS: list[Golden] = [
    Golden(
        id="rerank_best_fit",
        input="根据我的简历，最适合我投的岗位是哪些？",
        expected_tools=["rerank_by_resume"],
        expected_block_types=["job_cards"],
        comment="匹配重排意图",
    ),
    Golden(
        id="search_city_type",
        input="北京有哪些后端实习？",
        expected_tools=["search_jobs"],
        expected_block_types=["job_cards"],
        comment="城市+类型检索",
    ),
    Golden(
        id="search_company",
        input="字节跳动现在有什么岗位？",
        expected_tools=["search_jobs"],
        expected_block_types=["job_cards"],
        comment="按公司检索",
    ),
    Golden(
        id="daily_digest",
        input="今天有什么新岗位？优先级最高的是哪些？",
        expected_tools=["get_daily_digest"],
        comment="今日摘要/优先级",
    ),
    Golden(
        id="compare_two",
        input="字节跳动的后端实习和美团的后端校招，我该投哪个？",
        expected_tools=["compare_jobs"],
        comment="两岗对比；模型可能先 search 再 compare",
    ),
    Golden(
        id="preferences",
        input="我设置的求职偏好是什么？",
        expected_tools=["get_preferences"],
        comment="读取偏好",
    ),
]
