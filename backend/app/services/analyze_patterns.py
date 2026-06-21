"""拒信/转化模式分析：对标 career-ops analyze-patterns.mjs。"""
from __future__ import annotations

from collections import defaultdict

from app.services.application_store import list_applications


def analyze_patterns(client_id: str) -> dict:
    apps = list_applications(client_id)
    if not apps:
        return {
            "total": 0,
            "insights": [],
            "by_channel": {},
            "by_score_band": {},
            "rejection_rate": 0.0,
            "recommendations": ["暂无投递数据，完成评估后开始追踪"],
        }

    rejected = [a for a in apps if a.get("status") == "Rejected"]
    interviewed = [a for a in apps if a.get("status") in ("Interview", "Offer")]
    applied = [a for a in apps if a.get("status") not in ("Evaluated", "Discarded", "SKIP")]

    by_channel: dict[str, dict] = defaultdict(lambda: {"total": 0, "rejected": 0, "interview": 0})
    by_band: dict[str, dict] = defaultdict(lambda: {"total": 0, "rejected": 0})

    for a in apps:
        ch = a.get("channel", "未知")
        by_channel[ch]["total"] += 1
        if a.get("status") == "Rejected":
            by_channel[ch]["rejected"] += 1
        if a.get("status") in ("Interview", "Offer"):
            by_channel[ch]["interview"] += 1

        score = int(a.get("match_score") or 0)
        if score >= 80:
            band = "80+"
        elif score >= 60:
            band = "60-79"
        else:
            band = "<60"
        by_band[band]["total"] += 1
        if a.get("status") == "Rejected":
            by_band[band]["rejected"] += 1

    rejection_rate = len(rejected) / max(len(applied), 1)
    insights: list[str] = []
    recommendations: list[str] = []

    worst_ch = max(by_channel.items(), key=lambda x: x[1]["rejected"] / max(x[1]["total"], 1), default=None)
    if worst_ch and worst_ch[1]["rejected"] >= 2:
        insights.append(f"渠道「{worst_ch[0]}」拒信率较高（{worst_ch[1]['rejected']}/{worst_ch[1]['total']}）")
        recommendations.append(f"减少在「{worst_ch[0]}」的海投，优先补强匹配分 <80 的 gap")

    low_band = by_band.get("<60", {})
    if low_band.get("total", 0) >= 2 and low_band.get("rejected", 0) >= 1:
        insights.append("低匹配分（<60）岗位拒信偏多")
        recommendations.append("严格执行投递决策分，<60 分岗位先改简历再投")

    if len(interviewed) == 0 and len(applied) >= 3:
        insights.append("已投递但尚无面试转化")
        recommendations.append("检查简历关键词覆盖与项目量化表述，尝试提高匹配分 60+ 的岗位占比")

    if not insights:
        insights.append(f"共 {len(apps)} 条记录，拒信率 {rejection_rate:.0%}")

    if not recommendations:
        recommendations.append("保持当前策略，持续沉淀知识库与 STAR 故事")

    return {
        "total": len(apps),
        "applied_count": len(applied),
        "rejected_count": len(rejected),
        "interview_count": len(interviewed),
        "rejection_rate": round(rejection_rate, 3),
        "insights": insights,
        "by_channel": dict(by_channel),
        "by_score_band": dict(by_band),
        "recommendations": recommendations,
    }
