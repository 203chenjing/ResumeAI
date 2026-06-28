"""STAR 故事库：从 L1 知识库解析 + JD/archetype 语义召回（无硬编码关键词表）。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches

_STAR_HEADING = re.compile(r"^####\s+STAR\s*(?:[\d\w]+)?[：:]\s*(.+)$")
_LEGACY_HEADING = re.compile(r"^###\s+(.+)$")
_SECTION = re.compile(r"^##\s+(.+)$")
_META_LINE = re.compile(r"^>\s*story-id:\s*`([^`]+)`(.*)$", re.IGNORECASE)
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}")
_L2_MARKERS = ("L2", "投递策略", "JD 映射笔记", "archetype 金样")
_PRIORITY_RE = re.compile(r"priority:\s*(P[012])", re.I)
_ARCHETYPE_RE = re.compile(r"archetypes:\s*([^·]+)", re.I)
_EVIDENCE_RE = re.compile(r"evidence:\s*([^·]+)", re.I)
_RESUME_READY_RE = re.compile(r"resume-ready:\s*(yes|no)", re.I)


@dataclass
class Story:
    id: str
    title: str
    level: str = "L1"
    employer: str = ""
    project: str = ""
    role: str = ""
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""
    tags: list[str] = field(default_factory=list)
    fit_archetypes: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    resume_ready: bool = False
    priority: str = ""
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)


def _norm(text: str) -> str:
    return _WS.sub("", text or "").lower()


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text or ""))


def _token_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if inter == 0:
        return 0.0
    return inter / min(len(ta), len(tb))


def _similar(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.95
    return SequenceMatcher(None, na, nb).ratio()


def _split_csv(raw: str) -> list[str]:
    parts = re.split(r"[,，、]", raw or "")
    return [p.strip() for p in parts if p.strip()]


def _parse_meta_tail(tail: str) -> dict:
    tags = re.findall(r"#(\w+)", tail or "")
    m_pri = _PRIORITY_RE.search(tail or "")
    m_arc = _ARCHETYPE_RE.search(tail or "")
    m_ev = _EVIDENCE_RE.search(tail or "")
    m_rr = _RESUME_READY_RE.search(tail or "")
    archetypes = _split_csv(m_arc.group(1)) if m_arc else []
    evidence = _split_csv(m_ev.group(1).replace("`", "")) if m_ev else []
    return {
        "tags": tags,
        "priority": m_pri.group(1).upper() if m_pri else "",
        "fit_archetypes": archetypes,
        "evidence_ids": evidence,
        "resume_ready": bool(m_rr and m_rr.group(1).lower() == "yes"),
    }


def _extract_star(title: str, text: str, idx: int) -> Story:
    def grab(label: str) -> str:
        m = re.search(rf"\*\*{label}\*\*[：:]\s*(.+)", text)
        if m:
            return m.group(1).strip()
        m2 = re.search(rf"-\s*\*\*{label}\*\*[：:]\s*(.+)", text)
        return m2.group(1).strip() if m2 else ""

    inline_tags = re.findall(r"#(\w+)", text)
    return Story(
        id=f"s{idx}",
        title=title.strip(),
        situation=grab("背景") or grab("Situation"),
        task=grab("任务") or grab("Task"),
        action=grab("行动") or grab("Action"),
        result=grab("结果") or grab("Result"),
        reflection=grab("反思") or grab("Reflection"),
        tags=inline_tags,
    )


def _story_blob(story: Story) -> str:
    return " ".join(
        [
            story.title,
            story.employer,
            story.project,
            story.situation,
            story.task,
            story.action,
            story.result,
            story.reflection,
            " ".join(story.tags),
            " ".join(story.fit_archetypes),
        ]
    )


def _is_l2_section(name: str) -> bool:
    n = name or ""
    return any(m in n for m in _L2_MARKERS)


def _parse_employer_from_section(section: str) -> tuple[str, str]:
    """从 ## 标题解析 employer / project。"""
    s = (section or "").strip()
    if "｜" in s:
        parts = s.split("｜", 1)
        return parts[0].strip(), parts[1].strip()
    if "|" in s:
        parts = s.split("|", 1)
        return parts[0].strip(), parts[1].strip()
    return s, ""


def parse_stories_from_kb(knowledge_md: str) -> list[Story]:
    """从知识库 Markdown 解析 L1 STAR 块（#### STAR … + 可选 story-meta 行）。"""
    if not (knowledge_md or "").strip():
        return []

    stories: list[Story] = []
    section = ""
    employer, project = "", ""
    idx = 0

    lines = knowledge_md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        sec_m = _SECTION.match(line.strip())
        if sec_m:
            section = sec_m.group(1).strip()
            employer, project = _parse_employer_from_section(section)
            i += 1
            continue

        if _is_l2_section(section):
            i += 1
            continue

        star_m = _STAR_HEADING.match(line.strip())
        legacy_m = None if star_m else _LEGACY_HEADING.match(line.strip())

        if star_m or legacy_m:
            title = star_m.group(1) if star_m else legacy_m.group(1)  # type: ignore[union-attr]
            # 跳过「使用规则」类 ### 小标题
            if legacy_m and any(k in title for k in ("使用规则", "证据清单", "基本信息", "教育", "技能")):
                i += 1
                continue

            idx += 1
            body_lines: list[str] = []
            meta: dict = {}
            i += 1

            while i < len(lines) and not lines[i].strip():
                i += 1

            if i < len(lines):
                meta_m = _META_LINE.match(lines[i].strip())
                if meta_m:
                    meta = _parse_meta_tail(meta_m.group(2))
                    meta["id"] = meta_m.group(1).strip()
                    i += 1

            while i < len(lines):
                nxt = lines[i]
                if _SECTION.match(nxt.strip()) or _STAR_HEADING.match(nxt.strip()):
                    break
                if legacy_m and _LEGACY_HEADING.match(nxt.strip()) and body_lines:
                    break
                body_lines.append(nxt)
                i += 1

            body = "\n".join(body_lines)
            story = _extract_star(title, body, idx)
            story.id = meta.get("id") or story.id
            story.level = meta.get("level", "L1") if meta else story.level
            story.employer = employer
            story.project = project
            if meta:
                story.tags = list(dict.fromkeys(meta.get("tags", []) + story.tags))
                story.fit_archetypes = meta.get("fit_archetypes", [])
                story.evidence_ids = meta.get("evidence_ids", [])
                story.resume_ready = meta.get("resume_ready", False)
                story.priority = meta.get("priority", "")
            if story.situation or story.action or story.result:
                stories.append(story)
            continue

        i += 1

    if not stories and knowledge_md.strip():
        stories.append(
            Story(
                id="s0",
                title="综合经历",
                situation=knowledge_md[:300],
            )
        )
    return stories


def _archetype_match(query_archetype: str, story: Story) -> float:
    if not query_archetype or not story.fit_archetypes:
        return 0.0
    q = query_archetype.strip()
    for arc in story.fit_archetypes:
        if q in arc or arc in q:
            return 1.0
        if _similar(q, arc) >= 0.72:
            return 0.85
    close = get_close_matches(q, story.fit_archetypes, n=1, cutoff=0.6)
    return 0.7 if close else 0.0


def _priority_boost(story: Story) -> float:
    p = (story.priority or "").upper()
    if p == "P0":
        return 1.0
    if p == "P1":
        return 0.5
    if p == "P2":
        return 0.2
    return 0.0


def _score_story(
    story: Story,
    query: str,
    *,
    archetype: str = "",
) -> Story:
    blob = _story_blob(story)
    tag_blob = " ".join(story.tags + story.fit_archetypes)

    tok = _token_overlap(query, blob)
    seq = _similar(query, blob)
    tag_hits = _token_overlap(query, tag_blob)
    arc = _archetype_match(archetype, story)
    pri = _priority_boost(story)

    total = tok * 0.40 + seq * 0.25 + tag_hits * 0.15 + arc * 0.12 + pri * 0.08
    story.score = round(total, 4)
    story.score_breakdown = {
        "token": round(tok, 4),
        "sequence": round(seq, 4),
        "tags": round(tag_hits, 4),
        "archetype": round(arc, 4),
        "priority": round(pri, 4),
    }
    return story


def recall_stories(
    stories: list[Story],
    query: str,
    *,
    archetype: str = "",
    employer: str = "",
    top_k: int = 8,
    min_score: float = 0.12,
    resume_ready_only: bool = False,
) -> list[Story]:
    """按 JD 文本与可选 archetype 召回 top-K L1 故事（语义 + token，无关键词表）。"""
    if not stories:
        return []

    pool = stories
    if resume_ready_only:
        ready = [s for s in stories if s.resume_ready]
        pool = ready or stories

    if employer.strip():
        emp = employer.strip()
        filtered = [s for s in pool if emp in s.employer or _similar(emp, s.employer) >= 0.6]
        pool = filtered or pool

    scored = [_score_story(s, query, archetype=archetype) for s in pool]
    scored.sort(key=lambda s: s.score, reverse=True)
    hits = [s for s in scored if s.score >= min_score][:top_k]

    if hits:
        return hits

    # fallback：P0 优先，否则按原序
    p0 = [s for s in scored if (s.priority or "").upper() == "P0"]
    if p0:
        return p0[:top_k]
    return scored[:top_k]


def search_stories(stories: list[Story], query: str, top_k: int = 8) -> list[Story]:
    """兼容旧 API：等同 recall_stories。"""
    return recall_stories(stories, query, top_k=top_k)


def format_recall_context(stories: list[Story], *, max_chars: int = 6000) -> str:
    """将召回结果格式化为可注入 LLM prompt 的 Markdown。"""
    if not stories:
        return "（无召回条目，请使用完整知识库并勿编造事实。）"

    parts: list[str] = []
    used = 0
    for s in stories:
        block = (
            f"### [{s.id}] {s.title}\n"
            f"- 雇主：{s.employer or '—'} · 项目：{s.project or '—'}\n"
            f"- 匹配分：{s.score:.2f}（token={s.score_breakdown.get('token', 0):.2f}）\n"
            f"- **背景**：{s.situation or '—'}\n"
            f"- **任务**：{s.task or '—'}\n"
            f"- **行动**：{s.action or '—'}\n"
            f"- **结果**：{s.result or '—'}\n"
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def parse_l2_story_priorities(knowledge_md: str, archetype: str) -> list[str]:
    """从 L2-JD 映射笔记解析优先 story-id 列表（可选重排用）。"""
    if not archetype.strip():
        return []
    in_block = False
    ids: list[str] = []
    for line in knowledge_md.split("\n"):
        if line.strip().startswith("#### archetype：") or line.strip().startswith("#### archetype:"):
            in_block = archetype.strip() in line
            continue
        if in_block and line.strip().startswith("#### "):
            break
        if in_block:
            m = re.search(r"story-id[`：:]\s*[`\[{]?([a-zA-Z0-9_-]+)", line)
            if m:
                ids.append(m.group(1))
            ids.extend(re.findall(r"`([a-zA-Z0-9_-]+-\d+)`", line))
    return list(dict.fromkeys(ids))
