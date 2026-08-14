"""面经库：从秋招系统 articles 表加载真实面经，驱动模拟面试与面试准备。

对标牛客「AI 模拟面试 + 面经」：牛客靠自家题库，ResumeAI 复用秋招系统已聚合的
多源面经（牛客面经帖 + 搜狗微信面经文章 + 应届生面经），按公司/岗位/关键词召回，
让模拟面试问题更贴近真实面试，并支持「面试准备」侧的面经浏览。
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("D:/Users/qiujc/Downloads/秋招/data/qiuzhao.db")

# 面试问题信号：从面经文本中提取"被问到的问题"
# 1) "面试官问：xxx？" 句式
QUESTION_RE = re.compile(
    r"(?:面试官|一面|二面|HR|主管|leader)?.{0,8}?(?:问|提问|被问|问到|会问)[：:]?\s*"
    r"([^。\n？！?]{4,60}[？?])"
)
# 2) 编号列表："1.xxx" / "1、xxx" / "一、xxx" / "（1）xxx"
NUMBERED_QUESTION_RE = re.compile(
    r"(?:(?:\d{1,2}|[一二三四五六七八九十]+)[.、．)]\s*|（\d{1,2}）\s*)"
    r"([^。\n？?]{4,60}[？?]?)"
)
# 3) 高频面试问题句式（自我介绍/优缺点/项目/加班等）
KEYWORD_QUESTION_RE = re.compile(
    r"([^。\n？?]{0,12}(?:自我介绍|优缺点|职业规划|加班|出差|反问|遗憾|困难的事|抗压|为什么(?:来|选|考虑)|怎么(?:看|想|解决|改))[^。\n？?]{0,30}[？?]?)"
)
INTERVIEW_KEYWORDS = ("面经", "面试", "一面", "二面", "三面", "HR面", "技术面", "群面")

# 高频问题模板（面经里最常见的追问）
COMMON_QUESTIONS = (
    "请做一个 1 分钟的自我介绍。",
    "介绍一个你最有代表性的项目，并说明你在其中的角色。",
    "项目中遇到过最大的困难是什么？你是怎么解决的？",
    "为什么想来我们公司？对我们业务了解多少？",
    "你未来 3-5 年的职业规划是什么？",
    "讲一个你与团队协作中产生分歧的例子，最后怎么处理的？",
)


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return [str(t) for t in val if str(t).strip()] if isinstance(val, list) else []
    except Exception:
        return []


_NOISE_WORDS = (
    "投递", "时间线", "笔试", "开奖", "oc", "offer", "收到", "通过", "审批",
    "预约", "约了", "反问环节", "面试官", "一面：", "二面：", "HR面",
)


def _is_noise(q: str) -> bool:
    q = (q or "").strip()
    if not q or len(q) < 4:
        return True
    if q in ("自我介绍", "面试问题", "反问环节", "最后", "技术面", "HR面"):
        return True
    if q.startswith("（") or q.startswith("("):
        return True
    if any(t in q for t in _NOISE_WORDS) and not any(
        w in q for w in ("自我介绍", "优缺点", "加班", "出差", "职业规划")
    ):
        return True
    return False


# 逐行编号问题："1.xxx" "1、xxx" "一、xxx" "（1）xxx" "2、xxx"
_LINE_NUMBER_RE = re.compile(
    r"^\s*(?:\d{1,2}|[一二三四五六七八九十]+)[.、．)]\s*(.+)"
)
# 行内编号问题（牛客面经摘要常为单行："...1.介绍技术栈 2.询问日语..."）
_INLINE_NUMBER_RE = re.compile(
    r"(?:(?:\d{1,2}|[一二三四五六七八九十]+)[.、．)]|（\d{1,2}）)\s*"
    r"([^。\n？?]{3,55}?)(?=(?:\s*(?:\d{1,2}|[一二三四五六七八九十]+)[.、．)])|$)"
)
# 问号句（含"介绍下/说说/聊聊/为什么/怎么/是否/能不能"引导）
_ASK_RE = re.compile(
    r"(?:介绍|说说|聊聊|询问|问|为什么|怎么|是否|能不能|会问|被问)[^。\n？?]{2,50}[？?]"
)
# 关键词引导的无标点问题（"自我介绍"等）
_KEYWORD_LEAD_RE = re.compile(r"^(自我介绍|优缺点|职业规划|是否愿意加班|能不能接受出差|项目[^。\n]{0,20})")


def extract_questions(text: str) -> list[str]:
    """从面经文本中提取面试问题。

    牛客面经正文常见编号列表（1.介绍你的技术栈），逐行扫描提取；
    问句式（面试官问：xxx？）与关键词引导问题兜底。
    """
    if not text:
        return []
    found: list[str] = []

    # 问句式（原 QUESTION_RE）
    for m in QUESTION_RE.finditer(text):
        q = m.group(1).strip()
        if 4 <= len(q) <= 60 and q not in found:
            found.append(q)

    # 行内编号问题
    for m in _INLINE_NUMBER_RE.finditer(text):
        q = m.group(1).strip()
        if 4 <= len(q) <= 60 and q not in found and not _is_noise(q):
            found.append(q)
        if len(found) >= 8:
            break

    # 逐行扫描编号问题
    for line in text.splitlines():
        line = line.strip()
        m = _LINE_NUMBER_RE.match(line)
        q = ""
        if m:
            q = m.group(1).strip()
        elif _ASK_RE.search(line):
            q = _ASK_RE.search(line).group(0).strip()
        elif _KEYWORD_LEAD_RE.match(line):
            q = _KEYWORD_LEAD_RE.match(line).group(1).strip()
        if not q:
            continue
        q = q.strip("。，,、")
        if 4 <= len(q) <= 60 and q not in found and not _is_noise(q):
            found.append(q)
        if len(found) >= 8:
            break
    return found[:8]


class InterviewBank:
    """面经库：加载秋招系统面经并按公司/岗位/关键词召回。"""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self._articles: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._articles is not None:
            return self._articles
        if not self.db_path.is_file():
            logger.warning("面经库数据库不存在: %s", self.db_path)
            self._articles = []
            return self._articles
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT title, author, content_summary, source, source_url, category, tags "
                "FROM articles ORDER BY id DESC LIMIT 2000"
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.warning("读取面经库失败: %s", e)
            self._articles = []
            return self._articles

        items: list[dict] = []
        for r in rows:
            title = (r["title"] or "").strip()
            summary = (r["content_summary"] or "").strip()
            blob = f"{title} {summary}"
            if not any(k in blob for k in INTERVIEW_KEYWORDS):
                continue
            items.append(
                {
                    "title": title[:120],
                    "author": (r["author"] or "").strip(),
                    "summary": summary[:600],
                    "source": (r["source"] or "").strip(),
                    "source_url": (r["source_url"] or "").strip(),
                    "category": (r["category"] or "").strip(),
                    "tags": _parse_tags(r["tags"]),
                    "questions": extract_questions(f"{title}。{summary}"),
                }
            )
        self._articles = items
        logger.info("面经库加载 %d 条", len(items))
        return self._articles

    def search(self, query: str = "", *, company: str = "", limit: int = 5) -> list[dict]:
        """按公司/岗位/关键词召回相关面经。"""
        articles = self._load()
        if not articles:
            return []

        keywords = [q for q in (query, company) if q and q.strip()]
        if not keywords:
            return articles[:limit]

        scored: list[tuple[int, dict]] = []
        for a in articles:
            blob = " ".join(
                [
                    a["title"],
                    a["summary"],
                    a["category"],
                    " ".join(a["tags"]),
                ]
            )
            score = 0
            for kw in keywords:
                if kw in a["title"]:
                    score += 5
                elif kw in blob:
                    score += 2
            if score > 0:
                scored.append((score, a))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:limit]]

    def common_questions(self) -> list[str]:
        return list(COMMON_QUESTIONS)


# 全局单例（懒加载）
_bank: InterviewBank | None = None


def get_bank(db_path: str | Path | None = None) -> InterviewBank:
    global _bank
    if _bank is None or db_path is not None:
        _bank = InterviewBank(db_path=db_path)
    return _bank
