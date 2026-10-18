"""实习经历 numbered item 排版：保证 `N. **小标题**：正文` 格式。"""
from __future__ import annotations

import re

_NUM_PREFIX = re.compile(r"^(\d+)\.\s*")
_BOLD_ITEM = re.compile(r"^(\d+)\.\s*\*\*([^*]+)\*\*[：:]\s*")
# 被拍平成顶层编号的子要点：`2. **1）体验拆解**：…`
_SUB_ITEM = re.compile(r"^\*\*\s*[（(]?\s*(\d{1,2})\s*[）)]\s*(.+)$", re.S)


def demote_sub_item(text: str) -> str | None:
    """把被拍平的子要点还原成 `1）**标题**：正文`，不占顶层编号。

    解析与建议链路会把「项目 → 子要点」压成平级编号，既破坏结构，又让
    「每段经历 ≤5 条」规则误判（用户看到的是规则在指责自己）。
    """
    raw = (text or "").strip()
    num_m = _NUM_PREFIX.match(raw)
    if not num_m:
        return None
    rest = raw[num_m.end() :].strip()
    m = _SUB_ITEM.match(rest)
    if not m:
        return None

    num, tail = m.group(1), m.group(2).strip()
    # `**1）**体验拆解…**` 与 `**1）体验拆解**…` 两种坏形态都收敛到同一格式
    if not tail.startswith("**") and "**" in tail:
        tail = f"**{tail}"
    return f"{num}）{tail}"


def _split_title_body(rest: str) -> tuple[str, str] | None:
    for sep in ("：", ":"):
        if sep in rest:
            title, body = rest.split(sep, 1)
            title = title.strip().strip("*").strip()
            body = body.strip()
            if 2 <= len(title) <= 48 and body:
                return title, body
    return None


def format_numbered_item(num: str, title: str, body: str) -> str:
    title = title.strip().strip("*").strip()
    body = body.strip()
    return f"{num}. **{title}**：{body}"


def ensure_experience_item_format(text: str, *, reference: str = "") -> str:
    """将经历行规范为 `N. **小标题**：STAR…`；保留原编号。

    - 自带编号：以自身编号为准
    - 不带编号：沿用 reference 的编号（同一 bullet 的改写）
    - 自身没有小标题、但 reference 有：借用 reference 的小标题，
      仅限「编号来自 reference」的场景，避免把别的 bullet 标题套错
    """
    raw = (text or "").strip()
    if not raw:
        return raw

    ref = (reference or "").strip()
    ref_num = _NUM_PREFIX.match(ref)
    num_m = _NUM_PREFIX.match(raw)

    demoted = demote_sub_item(raw)
    if demoted:
        return demoted

    if _BOLD_ITEM.match(raw):
        return raw

    borrowed_ref = False
    if num_m:
        num, rest = num_m.group(1), raw[num_m.end() :]
    elif ref_num:
        num, rest = ref_num.group(1), raw
        borrowed_ref = True
    else:
        return raw

    split = _split_title_body(rest)
    if split:
        return format_numbered_item(num, split[0], split[1])

    if borrowed_ref:
        ref_split = _split_title_body(_NUM_PREFIX.sub("", ref))
        if ref_split:
            return format_numbered_item(num, ref_split[0], rest)

    return f"{num}. {rest}"


def normalize_experience_markdown(md: str) -> str:
    """遍历实习经历区块，规范 numbered item 行。"""
    if "## 实习经历" not in md:
        return md

    head, tail = md.split("## 实习经历", 1)
    exp_block, skills_tail = tail, ""
    if "## 相关技能" in tail:
        exp_block, skills_tail = tail.split("## 相关技能", 1)
        skills_tail = "## 相关技能" + skills_tail

    lines: list[str] = []
    for line in exp_block.split("\n"):
        stripped = line.strip()
        if _NUM_PREFIX.match(stripped):
            lines.append(ensure_experience_item_format(stripped))
        else:
            lines.append(line)

    return head + "## 实习经历" + "\n".join(lines) + skills_tail
