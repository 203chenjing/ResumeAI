"""超预算时的局部压缩：只压缩最长的几条 bullet，可撤销。

为什么不做整篇重写：用户已经逐条确认过建议，重写会让 30 多次决策作废。
这里只替换指定行，且要求新行更短、编号与标题格式不变，才允许落地。
"""
from __future__ import annotations

import logging
import re

from app.models.schemas import Session
from app.prompts.compress_resume import build_compress_prompt
from app.services.layout_budget import CHARS_PER_PAGE, char_count, layout_metrics
from app.services.llm_client import client
from app.services.resume_list_format import normalize_experience_markdown

logger = logging.getLogger(__name__)

_TARGET_RATIO = 0.88  # 压到容量 88%，给渲染误差留余量
_MAX_LINES_PER_ROUND = 8
_MAX_ROUNDS = 2
_NUM_PREFIX = re.compile(r"^(\d+)\.\s")
_SUB_PREFIX = re.compile(r"^[（(]?\s*(\d{1,2})\s*[）)]\s*")
_ITEM_LINE = re.compile(r"^(?:\d+\.\s|[（(]?\d{1,2}[）)])")
_MIN_LINE_LEN = 60  # 太短的 bullet 压不动，跳过


def _experience_lines(markdown: str) -> list[tuple[int, str]]:
    """返回 (行号, 内容) —— 实习经历里的顶层 bullet 与子要点都参与压缩。"""
    lines = markdown.split("\n")
    in_exp = False
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            in_exp = stripped.startswith("## 实习经历")
            continue
        if in_exp and _ITEM_LINE.match(stripped):
            out.append((i, stripped))
    return out


def _pick_targets(lines: list[tuple[int, str]], need_chars: int) -> list[tuple[int, str]]:
    """从最长的行开始挑，覆盖需要削减的字数。"""
    ranked = sorted(lines, key=lambda item: len(item[1]), reverse=True)
    picked: list[tuple[int, str]] = []
    covered = 0
    for item in ranked[:_MAX_LINES_PER_ROUND]:
        if len(item[1]) < _MIN_LINE_LEN:
            continue
        picked.append(item)
        covered += int(len(item[1]) * 0.3)  # 按可压缩 30% 估算
        if covered >= need_chars:
            break
    return picked


def _apply_rewrites(
    markdown: str, targets: list[tuple[int, str]], rewrites: list[dict]
) -> tuple[str, list[dict]]:
    lines = markdown.split("\n")
    by_id = {
        int(item["id"]): str(item.get("text") or "").strip()
        for item in rewrites
        if isinstance(item, dict) and item.get("id") is not None
    }
    changed: list[dict] = []

    for idx, (line_no, original) in enumerate(targets, start=1):
        candidate = by_id.get(idx)
        if not candidate or candidate == original:
            continue
        # 只接受「更短 + 编号一致」的改写，避免模型顺手重排结构
        if len(candidate) >= len(original):
            logger.info("compress: skip line %s (not shorter)", line_no)
            continue
        original_num = _NUM_PREFIX.match(original)
        if original_num:
            expected = f"{original_num.group(1)}. "
            if not candidate.startswith(expected):
                logger.info("compress: skip line %s (prefix mismatch)", line_no)
                continue
            if candidate.count("**") % 2 != 0:
                logger.info("compress: skip line %s (broken bold)", line_no)
                continue
        else:
            sub = _SUB_PREFIX.match(original)
            if sub and not candidate.startswith(sub.group(0).strip()):
                # 子要点必须保留自己的编号（1）2）…），否则层级会乱
                logger.info("compress: skip line %s (sub-item marker changed)", line_no)
                continue
        lines[line_no] = candidate
        changed.append({"before": original, "after": candidate, "saved": len(original) - len(candidate)})

    return "\n".join(lines), changed


def _render_pages(markdown: str, session_id: str) -> int | None:
    """真实渲染一次拿到页数（压缩是否够，以渲染为准，不靠字数估算）。"""
    from app.services.pdf_exporter import validate_resume_markdown

    try:
        validation = validate_resume_markdown(markdown, session_id=session_id)
    except Exception:
        logger.warning("compress: 页数校验失败，跳过", exc_info=True)
        return None
    return validation.get("page_count")


async def compress_to_page(sess: Session) -> dict:
    """压缩到一页：多轮只压长行，逐条替换，以真实渲染页数为准，可撤销。"""
    working = normalize_experience_markdown(sess.current_resume_md or "")
    before = layout_metrics(working)
    target_chars = int(CHARS_PER_PAGE * _TARGET_RATIO)
    all_changes: list[dict] = []
    pages: int | None = _render_pages(working, sess.session_id)

    for round_no in range(1, _MAX_ROUNDS + 1):
        need = char_count(working) - target_chars
        if need <= 0:
            break
        targets = _pick_targets(_experience_lines(working), need)
        if not targets:
            break

        payload = [
            {"id": i, "text": text, "max_len": max(_MIN_LINE_LEN, int(len(text) * 0.72))}
            for i, (_, text) in enumerate(targets, start=1)
        ]
        system, user = build_compress_prompt(payload, target_chars, round_no=round_no)
        data = await client.chat_json(system, user, temperature=0.25, max_tokens=6000)
        rewrites = data.get("items") or data.get("rewrites") or []

        working, changed = _apply_rewrites(working, targets, rewrites)
        all_changes.extend(changed)
        logger.info(
            "compress round=%d targets=%d applied=%d saved=%d need=%d",
            round_no,
            len(targets),
            len(changed),
            sum(c["saved"] for c in changed),
            need,
        )
        if not changed:
            break
        pages = _render_pages(working, sess.session_id)
        if pages is not None and pages <= 1:
            break

    removed = sum(c["saved"] for c in all_changes)
    if all_changes:
        if sess.finalize_status == "finalized":
            sess.finalize_status = "stale"
        sess.pre_compress_md = sess.current_resume_md
        sess.current_resume_md = working

    after = layout_metrics(working)
    logger.info(
        "compress session=%s lines=%d removed=%d chars=%d->%d pages=%s",
        sess.session_id,
        len(all_changes),
        removed,
        before["char_count"],
        after["char_count"],
        pages,
    )
    return {
        "markdown": working,
        "changed": all_changes,
        "removed_chars": removed,
        "before": before,
        "after": after,
        "page_count": pages,
        "reached_target": pages is not None and pages <= 1,
        "remaining_chars": max(0, after["char_count"] - target_chars),
    }
