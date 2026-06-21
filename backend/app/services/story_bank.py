"""STAR 故事库 + 关键词检索：对标 career-ops story-bank（Qdrant 可选，默认内存检索）。"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Story:
    id: str
    title: str
    situation: str
    task: str
    action: str
    result: str
    reflection: str
    tags: list[str]
    score: float = 0.0


def parse_stories_from_kb(knowledge_md: str) -> list[Story]:
    """从知识库 Markdown 解析 STAR 块。"""
    stories: list[Story] = []
    blocks = re.split(r"\n###\s+", knowledge_md)
    for i, block in enumerate(blocks[1:], 1):
        lines = block.strip().split("\n")
        title = lines[0].strip() if lines else f"故事 {i}"
        text = "\n".join(lines[1:])
        s = _extract_star(title, text, i)
        if s.situation or s.action or s.result:
            stories.append(s)
    if not stories and knowledge_md.strip():
        stories.append(
            Story(
                id="s0",
                title="综合经历",
                situation=knowledge_md[:300],
                task="",
                action="",
                result="",
                reflection="",
                tags=[],
            )
        )
    return stories


def _extract_star(title: str, text: str, idx: int) -> Story:
    def grab(label: str) -> str:
        m = re.search(rf"\*\*{label}\*\*[：:]\s*(.+)", text)
        if m:
            return m.group(1).strip()
        m2 = re.search(rf"-\s*\*\*{label}\*\*[：:]\s*(.+)", text)
        return m2.group(1).strip() if m2 else ""

    tags = re.findall(r"#(\w+)", text)
    return Story(
        id=f"s{idx}",
        title=title,
        situation=grab("背景") or grab("Situation"),
        task=grab("任务") or grab("Task"),
        action=grab("行动") or grab("Action"),
        result=grab("结果") or grab("Result"),
        reflection=grab("反思") or grab("Reflection"),
        tags=tags,
    )


def search_stories(stories: list[Story], query: str, top_k: int = 8) -> list[Story]:
    """简单关键词相关度（无向量库时的 fallback）。"""
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}", query.lower()))
    if not q_tokens:
        return stories[:top_k]

    scored: list[Story] = []
    for s in stories:
        blob = " ".join([s.title, s.situation, s.task, s.action, s.result, " ".join(s.tags)]).lower()
        hits = sum(1 for t in q_tokens if t in blob)
        s.score = hits / max(len(q_tokens), 1)
        scored.append(s)
    scored.sort(key=lambda x: x.score, reverse=True)
    return [s for s in scored if s.score > 0][:top_k] or stories[:top_k]
