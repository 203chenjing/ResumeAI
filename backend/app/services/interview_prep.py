"""面试准备包：对标 career-ops interview-prep。"""
from __future__ import annotations

from app.services.story_bank import Story, parse_stories_from_kb, search_stories

HR_QUESTIONS = [
    "请做一个自我介绍（1-2 分钟）",
    "为什么选择我们公司/这个岗位？",
    "你的优缺点是什么？",
    "未来 3-5 年职业规划？",
    "如何处理团队冲突？",
]

TECH_QUESTIONS = [
    "介绍一个你最有成就感的项目",
    "项目中遇到的最大技术挑战是什么？",
    "如何保证代码/数据质量？",
    "描述一次性能优化经历",
]

GROUP_QUESTIONS = [
    "无领导小组：资源有限时如何排序需求？",
    "团队意见分歧时你如何推动结论？",
]


def _story_fit(story: Story | None, question: str) -> str:
    if not story:
        return "none"
    if story.score >= 0.5:
        return "strong"
    if story.score > 0:
        return "partial"
    return "none"


def build_prep_pack(
    *,
    jd_text: str,
    company: str,
    role: str,
    knowledge_md: str,
) -> dict:
    stories = parse_stories_from_kb(knowledge_md)
    query = f"{company} {role} {jd_text[:500]}"
    top_stories = search_stories(stories, query, top_k=8)

    def pack_questions(questions: list[str], category: str) -> list[dict]:
        items = []
        for q in questions:
            best = top_stories[0] if top_stories else None
            items.append(
                {
                    "question": q,
                    "category": category,
                    "story_fit": _story_fit(best, q),
                    "suggested_story_id": best.id if best else "",
                    "suggested_story_title": best.title if best else "",
                    "tips": _tips_for(q, best),
                }
            )
        return items

    return {
        "company": company,
        "role": role,
        "stories": [
            {
                "id": s.id,
                "title": s.title,
                "situation": s.situation,
                "task": s.task,
                "action": s.action,
                "result": s.result,
                "reflection": s.reflection,
                "tags": s.tags,
                "relevance": round(s.score, 2),
            }
            for s in top_stories
        ],
        "questions": {
            "hr": pack_questions(HR_QUESTIONS, "hr"),
            "technical": pack_questions(TECH_QUESTIONS, "technical"),
            "group": pack_questions(GROUP_QUESTIONS, "group"),
        },
    }


def _tips_for(question: str, story: Story | None) -> str:
    if not story:
        return "建议从知识库补充 STAR 故事后再练"
    if "项目" in question or "挑战" in question:
        return f"用「{story.title}」展开 Action + 量化 Result"
    if "自我介绍" in question:
        return "结构：背景 → 核心能力 → 与岗位匹配点"
    return f"可关联故事：{story.title}"
