"""定稿预检：把「最后一步被打回」提前成随时可跑的一次体检。

输出结构化问题（code / message / hint / action），前端据此渲染可操作卡片，
而不是一句「定稿未通过校验：…」。
"""
from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict

from app.models.schemas import Session
from app.services.layout_budget import EXPERIENCE_ITEM_LIMIT, SKILL_ITEM_LIMIT, layout_metrics
from app.services.pdf_exporter import validate_resume_markdown
from app.services.resume_list_format import normalize_experience_markdown

logger = logging.getLogger(__name__)

_CACHE: OrderedDict[str, dict] = OrderedDict()
_CACHE_MAX = 32

# 前端可执行动作
ACTION_COMPRESS = "compress"  # 一键压缩到一页
ACTION_EDIT = "edit"  # 回改稿页处理
ACTION_NONE = "none"


def _issue(code: str, message: str, hint: str, action: str = ACTION_NONE, blocking: bool = True) -> dict:
    return {"code": code, "message": message, "hint": hint, "action": action, "blocking": blocking}


def _hint_for_skill_issue(text: str) -> tuple[str, str]:
    """把自检文案翻译成「下一步做什么」。"""
    if "编号项" in text:
        return f"每段经历建议不超过 {EXPERIENCE_ITEM_LIMIT} 条；项目下的子要点会放在同一项目里展示", ACTION_EDIT
    if "相关技能" in text:
        return f"技能固定 4 条：工作技能 / 数据技能 / AI技能 / 语言能力（当前需 {SKILL_ITEM_LIMIT} 条）", ACTION_EDIT
    if "分隔线" in text:
        return "章节之间补一行 `---`，导出排版靠它分节", ACTION_EDIT
    if "总结块" in text:
        return "删掉「求职优势 / 个人总结」类总结块，内容并入经历要点", ACTION_EDIT
    if "无序列表" in text:
        return "经历改用 `1. 2. 3.` 有序列表", ACTION_EDIT
    return "按提示调整格式后重新预检", ACTION_EDIT


def build_issues(validation: dict, metrics: dict) -> list[dict]:
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(code: str, message: str, hint: str, action: str, blocking: bool = True) -> None:
        key = (code, message)
        if key in seen:
            return
        seen.add(key)
        issues.append(_issue(code, message, hint, action, blocking))

    for text in validation.get("skill_issues") or []:
        hint, action = _hint_for_skill_issue(text)
        add("skill", text, hint, action)

    page_count = validation.get("page_count") or 0
    if page_count > 1:
        add(
            "page_count",
            f"当前 {page_count} 页，标准版要求 1 页",
            "可以先「AI 压到一页」，或确认后按当前页数导出",
            ACTION_COMPRESS,
        )

    for text in validation.get("layout_issues") or []:
        if "留白" in text:
            add("bottom_gap", text, "内容偏少；补一条与 JD 相关的量化成果更划算", ACTION_EDIT, blocking=False)
        elif "渲染" in text or "不可用" in text:
            add("render_unavailable", text, "在后端执行 `python -m playwright install chromium` 后重试", ACTION_NONE)
        elif "页" in text:
            # 页数问题已由 page_count 统一表达，避免同一件事报两遍
            continue
        else:
            add("layout", text, "按提示调整后重新预检", ACTION_EDIT)

    if metrics.get("char_count", 0) < 1200:
        add(
            "too_sparse",
            f"正文约 {metrics['char_count']} 字，偏少",
            "一页简历通常 1500-2400 字；补经历细节比堆形容词有效",
            ACTION_EDIT,
            blocking=False,
        )

    return issues


def _cache_key(markdown: str, session_id: str) -> str:
    return hashlib.sha1(f"{session_id}:{markdown}".encode("utf-8")).hexdigest()


# 无论是否 force 都必须拦下的硬故障（PDF 压根生成不出来）
_HARD_CODES = {"render_unavailable", "layout"}


def blocking_issues(validation: dict, metrics: dict, *, force: bool = False) -> list[dict]:
    """定稿阻断项。

    force=True 表示用户明确接受「非一页」结果，此时只保留渲染类硬故障，
    其余降级为提示——产品承诺是「帮你改到能投」，不是「替你决定什么能投」。
    """
    issues = build_issues(validation, metrics)
    if force:
        return [i for i in issues if i["code"] in _HARD_CODES]
    return [i for i in issues if i["blocking"]]


def run_preflight(sess: Session) -> dict:
    """真实渲染一次（约 1-3s），结果按内容哈希缓存，重复调用瞬时返回。"""
    markdown = normalize_experience_markdown(sess.current_resume_md or "")
    metrics = layout_metrics(markdown)
    key = _cache_key(markdown, sess.session_id)

    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached

    validation = validate_resume_markdown(markdown, session_id=sess.session_id)
    issues = build_issues(validation, metrics)
    result = {
        "passed": not any(i["blocking"] for i in issues),
        "page_count": validation.get("page_count"),
        "metrics": metrics,
        "issues": issues,
        "checked_markdown": markdown,
    }

    _CACHE[key] = result
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    logger.info(
        "preflight session=%s pages=%s issues=%d passed=%s",
        sess.session_id,
        result["page_count"],
        len(issues),
        result["passed"],
    )
    return result
