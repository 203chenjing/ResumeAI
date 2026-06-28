"""按 JD 岗位原型生成「叙事视角」提示，驱动经历改写而非仅贴关键词。"""
from __future__ import annotations

import json
from difflib import get_close_matches
from typing import Any

# 叙事镜头配置（岗位类型 → 改写原则）。岗位类型来自 JD 分析的 archetype 字段，不用用户措辞匹配。
ROLE_LENS: dict[str, dict[str, Any]] = {
    "项目管理": {
        "emphasis": "范围/里程碑/排期/资源协调/干系人/风险与变更/交付验收/推进闭环",
        "verbs": "统筹、拆解、排期、协调、跟踪、推进、验收、闭环、识别风险",
        "reframe": (
            "原文若偏产品（需求/PRD/用户洞察/功能设计），改写成：项目目标→范围拆解→多方协同→"
            "风险与排期→交付结果。保留真实事实，换项目管理叙事，不要只换同义词。"
        ),
        "example": (
            "产品侧「输出 AI 产品 PRD」→ 项目侧「拆解模块范围与里程碑，协调算法/前端/合规评审并推动按期交付」"
        ),
    },
    "软件产品经理": {
        "emphasis": "用户场景/需求拆解/PRD/方案权衡/数据验证/迭代/跨团队协同/业务结果",
        "verbs": "调研、定义、设计、输出、验证、迭代、推动、落地",
        "reframe": "突出问题-方案-验证-结果；写清用户/场景与业务指标，少写纯项目排期话术。",
        "example": "协调评审 → 定义需求边界并输出 PRD，推动方案在搜索场景落地",
    },
    "AI产品经理": {
        "emphasis": "AI场景/触发规则/Prompt或策略/评估指标/人机协同/合规与降级/效果验证",
        "verbs": "定义、设计、约束、评估、迭代、治理、落地",
        "reframe": "写清 AI 能力边界、输入输出、评估与风险控制；避免空泛「AI赋能」。",
        "example": "做摘要功能 → 定义触发规则与 Prompt 约束，离线评估准确率后灰度上线",
    },
    "数据分析": {
        "emphasis": "指标定义/取数分析/归因/看板/实验/A-B/结论驱动决策",
        "verbs": "分析、拆解、建模、监控、归因、验证、输出",
        "reframe": "把业务动作改写成可量化分析链路：问题→数据→方法→结论→行动。",
        "example": "优化转化 → 搭建漏斗指标并 A/B 验证，定位流失环节后推动策略调整",
    },
    "运营": {
        "emphasis": "用户分层/活动机制/转化/留存/内容策略/渠道协同/效果复盘",
        "verbs": "策划、推广、转化、复盘、优化、协同、拉动",
        "reframe": "强调用户行为与业务结果，写活动/机制/转化，少写底层技术实现。",
        "example": "",
    },
    "通用": {
        "emphasis": "JD core_requirements 与 ranking.核心匹配 中的动作与结果",
        "verbs": "按 JD 常用强动词",
        "reframe": "先识别 JD 岗位类型，再选择对应叙事镜头；禁止仅句尾贴 JD 关键词。",
        "example": "",
    },
}

_BUCKET_KEYS = [k for k in ROLE_LENS if k != "通用"]


def infer_role_bucket(archetype: str = "", role: str = "") -> str:
    """从 JD 分析产出的 archetype/role 映射叙事镜头（不扫描用户消息关键词）。"""
    for raw in (archetype.strip(), role.strip()):
        if not raw:
            continue
        if raw in ROLE_LENS:
            return raw
        close = get_close_matches(raw, _BUCKET_KEYS, n=1, cutoff=0.55)
        if close:
            return close[0]
        for key in _BUCKET_KEYS:
            if key in raw or raw in key:
                return key
    return "通用"


def build_role_lens_section(jd: dict[str, Any] | str | None) -> str:
    """生成注入 suggestion/chat/resume  prompt 的岗位视角块。"""
    if jd is None:
        jd = {}
    elif isinstance(jd, str):
        try:
            jd = json.loads(jd)
        except Exception:
            jd = {}

    role = str(jd.get("role") or "").strip()
    archetype = str(jd.get("archetype") or "").strip()
    bucket = infer_role_bucket(archetype, role)
    lens = ROLE_LENS.get(bucket, ROLE_LENS["通用"])

    core = jd.get("core_requirements") or []
    ranking_core = (jd.get("ranking") or {}).get("核心匹配") or []
    must_hit = list(dict.fromkeys([*ranking_core[:4], *core[:4]]))[:6]

    lines = [
        "==== 目标岗位叙事视角（硬性：经历改写须符合此镜头）====",
        f"岗位：{role or '（未识别）'}",
        f"原型：{archetype or bucket}",
        f"叙事镜头：{bucket}",
        f"优先强调：{lens['emphasis']}",
        f"推荐动词：{lens['verbs']}",
        f"改写原则：{lens['reframe']}",
    ]
    if lens.get("example"):
        lines.append(f"示例：{lens['example']}")
    if must_hit:
        lines.append(f"JD 核心命中点（每条 star 建议至少覆盖其一）：{'；'.join(must_hit)}")
    lines.append(
        "若原文叙事与目标岗位不一致，必须用 star 类建议整句重写视角，"
        "不得仅在句尾追加「体现XX」。"
    )
    lines.append("==== 叙事视角结束 ====")
    return "\n".join(lines)
