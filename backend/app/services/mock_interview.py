"""模拟面试 SSE：对标 career-ops interview + JobHunter orchestrator。"""
from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator

from app.config import settings
from app.services.llm_client import client
from app.services.pending_knowledge import extract_pending_from_diff

ROUNDS = {
    "hr": "HR 面",
    "technical": "技术面",
    "group": "群面",
}

FALLBACK_QUESTIONS = {
    "hr": [
        "请做一个 1 分钟的自我介绍。",
        "你为什么想加入我们公司？",
    ],
    "technical": [
        "介绍一个你最有代表性的项目。",
        "项目中你负责的核心模块是什么？",
    ],
    "group": [
        "如果团队对方案有分歧，你会如何处理？",
    ],
}

PLACEHOLDER_RE = re.compile(
    r"^(?:x{2,}|测试+|不知道|无|没有|随便|略|\.{2,}|哈{2,}|嗯{2,}|啊{2,})$",
    re.IGNORECASE,
)

INTERVIEW_EVAL_SYSTEM = """你是严格的秋招面试官，负责评估候选人的面试回答。

评分原则（必须遵守）：
1. 回答过短（少于 20 字）、敷衍（如「xx」「不知道」「随便」）、无具体事实 → star_score 必须在 0-25，不得虚假表扬。
2. 缺少 STAR 结构或无量化结果 → star_score 通常在 25-55，指出缺什么。
3. 有具体情境、行动和量化结果 → 才可给 60 分以上。
4. feedback 格式：优点：（无则写「暂无」）\\n改进点：...

输出 JSON 字段：feedback, star_score(0-100), next_question, excellent_snippet（仅当 score>=75 时填写可沉淀的优秀表述，否则空字符串）"""


def assess_answer_quality(answer: str) -> dict[str, Any]:
    """规则层：识别无效/敷衍回答，避免 LLM 幻觉式好评。"""
    text = (answer or "").strip()
    if not text:
        return {"valid": False, "reason": "empty", "score": 0}

    compact = re.sub(r"\s+", "", text)
    if PLACEHOLDER_RE.match(compact) or PLACEHOLDER_RE.match(text):
        return {"valid": False, "reason": "placeholder", "score": 8}

    # 重复单字符或极短无意义串
    letters = re.sub(r"[\W\d_]", "", compact)
    if len(letters) <= 4 and len(compact) < 30:
        return {"valid": False, "reason": "placeholder", "score": 10}

    if len(set(letters)) <= 2 and len(letters) < 15:
        return {"valid": False, "reason": "placeholder", "score": 12}

    if len(text) < 20:
        return {"valid": False, "reason": "too_short", "score": max(5, len(text))}

    star_hits = sum(1 for kw in ("背景", "任务", "行动", "结果", "负责", "实现", "提升", "优化") if kw in text)
    if len(text) < 50 and star_hits == 0 and not re.search(r"\d", text):
        return {"valid": False, "reason": "no_substance", "score": 20}

    return {"valid": True, "reason": "ok", "score": None}


def _invalid_feedback(reason: str, question: str) -> str:
    tips = {
        "empty": "你还没有作答。",
        "too_short": "回答过短，无法判断你的真实能力。",
        "placeholder": "回答过于敷衍，不像正式面试表述。",
        "no_substance": "缺少具体情境、行动或结果，信息不足。",
    }
    lead = tips.get(reason, "回答不合格。")
    return (
        f"{lead}\n"
        f"优点：暂无。\n"
        f"改进点：请用 STAR 结构重新回答本题——情境（Situation）/ 任务（Task）/ "
        f"行动（Action）/ 结果（Result，尽量含量化指标）。\n"
        f"题目：{question}"
    )


async def stream_mock_interview(
    *,
    round_type: str,
    jd_text: str,
    company: str,
    role: str,
    user_answer: str,
    turn: int,
    client_id: str = "default",
) -> AsyncGenerator[dict, None]:
    round_label = ROUNDS.get(round_type, "面试")
    questions = FALLBACK_QUESTIONS.get(round_type, FALLBACK_QUESTIONS["hr"])
    q_idx = min(turn, len(questions) - 1)
    question = questions[q_idx]

    if turn == 0 and not user_answer.strip():
        prompt = f"【{round_label}】{question}\n\n请用 STAR 结构回答（情境 / 任务 / 行动 / 结果）。"
        yield {
            "type": "done",
            "reply": prompt,
            "question": question,
            "turn": turn,
            "score": None,
            "feedback": "",
        }
        return

    quality = assess_answer_quality(user_answer)
    if not quality["valid"]:
        feedback = _invalid_feedback(quality["reason"], question)
        score = int(quality["score"] or 15)
        yield {"type": "text", "content": feedback}
        yield {
            "type": "done",
            "reply": feedback,
            "question": question,
            "turn": turn,
            "score": score,
            "feedback": feedback,
        }
        return

    if settings.deepseek_api_key and user_answer.strip():
        user = json.dumps(
            {
                "company": company,
                "role": role,
                "round": round_label,
                "jd_excerpt": jd_text[:600],
                "question": question,
                "answer": user_answer,
                "turn": turn,
            },
            ensure_ascii=False,
        )
        try:
            data = await client.chat_json(INTERVIEW_EVAL_SYSTEM, user, temperature=0.2)
            feedback = (data.get("feedback") or "").strip() or _rule_feedback(user_answer)
            score = int(data.get("star_score", _rule_score(user_answer)))

            # 二次校验：LLM 仍给高分时压分
            if len(user_answer.strip()) < 40 and score > 35:
                score = 30
                feedback = _invalid_feedback("too_short", question)

            next_q = data.get("next_question") or questions[min(q_idx + 1, len(questions) - 1)]
            snippet = (data.get("excellent_snippet") or "").strip()

            yield {"type": "text", "content": feedback}
            if snippet and score >= 75:
                extract_pending_from_diff(
                    client_id=client_id,
                    source="mock_interview",
                    original_text="",
                    new_text=snippet,
                    context=f"{company}-{role}-{round_label}",
                )
            yield {
                "type": "done",
                "reply": feedback,
                "question": next_q,
                "turn": turn + 1,
                "score": score,
                "feedback": feedback,
                "excellent_snippet": snippet,
            }
            return
        except Exception:
            pass

    feedback = _rule_feedback(user_answer)
    score = _rule_score(user_answer)
    next_q = questions[min(q_idx + 1, len(questions) - 1)]
    yield {"type": "text", "content": feedback}
    if score >= 75 and len(user_answer) > 80:
        extract_pending_from_diff(
            client_id=client_id,
            source="mock_interview",
            original_text="",
            new_text=user_answer[:400],
            context=f"{company}-{role}",
        )
    yield {
        "type": "done",
        "reply": feedback,
        "question": next_q,
        "turn": turn + 1,
        "score": score,
        "feedback": feedback,
    }


def _rule_score(answer: str) -> int:
    score = 35
    if len(answer) > 60:
        score += 15
    if len(answer) > 120:
        score += 10
    for kw in ("结果", "提升", "%", "负责", "优化", "实现", "背景", "任务", "行动"):
        if kw in answer:
            score += 5
    return min(95, score)


def _rule_feedback(answer: str) -> str:
    if len(answer) < 40:
        return (
            "优点：暂无。\n"
            "改进点：回答偏短，请补充 STAR 四要素，并给出至少 1 个量化结果（数字、百分比或影响范围）。"
        )
    if "结果" not in answer and "%" not in answer and not re.search(r"\d", answer):
        return "优点：有一定表述。\n改进点：请补充 Result 中的量化成果（数字、百分比、影响范围）。"
    return "优点：结构较清晰。\n改进点：可再突出与目标岗位的匹配点，并准备追问细节。"
