"""工具注册表：按当前会话状态动态暴露可用能力（非写死流水线）。"""
from __future__ import annotations

from app.models.schemas import Session
from app.services.resume_density import assess_density

# 元数据：供 Planner 动态注入 Prompt
TOOL_CATALOG: dict[str, dict] = {
    "get_state": {
        "desc": "读取当前会话：建议数、pending、定稿状态、密度、匹配度",
        "specialists": ["analyzer", "writer", "qa", "coordinator"],
        "risky": False,
    },
    "analyze_jd": {
        "desc": "分析 JD（需会话中有 jd_text 且尚未分析）",
        "specialists": ["analyzer", "coordinator"],
        "risky": False,
    },
    "analyze_match": {
        "desc": "计算简历与 JD 匹配度（需已完成 JD 分析）",
        "specialists": ["analyzer", "coordinator"],
        "risky": False,
    },
    "save_knowledge_base": {
        "desc": "保存知识库内容到会话（content 可省略则用会话已有）",
        "specialists": ["writer", "coordinator"],
        "risky": False,
    },
    "init_knowledge_from_resume": {
        "desc": "从当前简历初始化知识库草稿（只搬运事实，不润色）",
        "specialists": ["writer", "coordinator"],
        "risky": False,
    },
    "expand_star": {
        "desc": "补全单段 STAR 故事",
        "specialists": ["writer", "coordinator"],
        "risky": False,
        "input_hint": {"section_title": "标题", "content": "段落内容", "hint": "用户补充"},
    },
    "audit_knowledge": {
        "desc": "审计知识库缺失指标与待确认项",
        "specialists": ["analyzer", "coordinator"],
        "risky": False,
    },
    "build_resume_from_knowledge": {
        "desc": "根据知识库与目标岗位重新生成工作稿简历（覆盖当前工作稿，并重新生成建议）",
        "specialists": ["writer", "coordinator"],
        "risky": True,
        "input_hint": {"regenerate_suggestions": True},
    },
    "generate_suggestions": {
        "desc": "基于当前简历与 JD 生成修改建议",
        "specialists": ["writer", "coordinator"],
        "risky": False,
    },
    "review_suggestions": {
        "desc": "批量处理 pending 建议；policy 由用户偏好或你根据交互决定",
        "specialists": ["qa", "coordinator"],
        "risky": True,
        "input_hint": {"policy": "accept_safe|accept_all|reject_all_pending"},
    },
    "finalize_resume": {
        "desc": "将工作稿定稿为可导出版本（需无 pending）",
        "specialists": ["qa", "coordinator"],
        "risky": True,
    },
    "prepare_export": {
        "desc": "检查是否可导出 PDF（需已定稿）",
        "specialists": ["qa", "coordinator"],
        "risky": True,
    },
    "update_preferences": {
        "desc": "根据用户本轮交互更新长期偏好/备注（写入用户记忆）",
        "specialists": ["writer", "qa", "coordinator"],
        "risky": False,
        "input_hint": {
            "writing_style": "string",
            "review_policy": "accept_safe|accept_all|reject_all_pending",
            "notes": "string",
            "recent_intent": "用户常用指令摘要",
        },
    },
    "finish": {
        "desc": "结束本轮 Agent，向用户汇报 summary",
        "specialists": ["analyzer", "writer", "qa", "coordinator"],
        "risky": False,
    },
}

RISKY_TOOLS = {name for name, meta in TOOL_CATALOG.items() if meta.get("risky")}


def is_risky_tool(action: str) -> bool:
    return (action or "").strip() in RISKY_TOOLS


def available_tools(sess: Session, specialist: str = "coordinator") -> list[dict]:
    """按会话真实状态 + 角色过滤，返回当前可调用的工具列表。"""
    out: list[dict] = []
    density = assess_density(sess.current_resume_md)

    for name, meta in TOOL_CATALOG.items():
        if specialist != "coordinator" and specialist not in meta.get("specialists", []):
            continue
        if name == "analyze_jd" and (not sess.jd_text.strip() or sess.jd_analysis):
            if sess.jd_analysis:
                continue  # 已完成则不再暴露，避免重复
            if not sess.jd_text.strip():
                continue
        if name == "analyze_match" and (not sess.jd_analysis or not sess.current_resume_md):
            continue
        if name == "init_knowledge_from_resume" and not (
            sess.current_resume_md or sess.original_resume_md
        ):
            continue
        if name == "expand_star" and not sess.knowledge_base_md.strip():
            continue
        if name == "audit_knowledge" and not sess.knowledge_base_md.strip():
            continue
        if name == "build_resume_from_knowledge" and not sess.jd_analysis:
            continue
        if name == "generate_suggestions" and not sess.match_result:
            continue
        if name == "review_suggestions" and not any(s.status == "pending" for s in sess.suggestions):
            continue
        if name == "finalize_resume" and sess.finalize_status == "finalized":
            continue
        if name == "prepare_export" and sess.finalize_status != "finalized":
            continue
        out.append({
            "name": name,
            "description": meta["desc"],
            "input_hint": meta.get("input_hint"),
        })

    out.append({
        "name": "_session_snapshot",
        "description": "只读",
        "snapshot": {
            "status": sess.status,
            "pending": len([s for s in sess.suggestions if s.status in ("pending", "adjusted")]),
            "suggestions_total": len(sess.suggestions),
            "finalize_status": sess.finalize_status,
            "has_jd": bool(sess.jd_analysis),
            "has_match": bool(sess.match_result),
            "density_status": density.get("status"),
            "char_count": density.get("char_count"),
        },
    })
    return out


def tools_prompt_block(sess: Session, specialist: str = "coordinator") -> str:
    tools = available_tools(sess, specialist)
    lines = ["当前可调用的工具（仅能从下列选择，勿编造）："]
    for t in tools:
        if t["name"].startswith("_"):
            lines.append(f"- 会话快照：{t.get('snapshot')}")
            continue
        hint = f" 参数示例: {t['input_hint']}" if t.get("input_hint") else ""
        lines.append(f"- {t['name']}: {t['description']}{hint}")
    return "\n".join(lines)
