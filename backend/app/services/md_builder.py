"""简历 Markdown 重建：从 ParsedResume 生成符合 SKILL.md 排版规范的 Markdown。"""
from app.models.schemas import ParsedResume


def build_resume_markdown(parsed: ParsedResume, photo_path: str = "") -> str:
    """按 resume-template.md 规范生成 Markdown。"""
    lines: list[str] = []

    # Header
    h = parsed.header
    lines.append(f"# {h.name or '[姓名]'}")
    lines.append("")
    contact_parts = []
    if h.phone:
        contact_parts.append(f"**{h.phone}**")
    if h.email:
        contact_parts.append(h.email)
    if h.location or h.target_role:
        loc_role = " / ".join([x for x in [h.location, h.target_role] if x])
        if loc_role:
            contact_parts.append(loc_role)
    if contact_parts:
        lines.append(" · ".join(contact_parts))
        lines.append("")
    if photo_path:
        lines.append(f"![个人照片]({photo_path})")
        lines.append("")

    # Education
    lines.append("## 教育经历")
    lines.append("")
    for edu in parsed.education:
        title_parts = []
        if edu.college:
            title_parts.append(edu.college)
        if edu.degree:
            title_parts.append(edu.degree)
        line1 = f"**{edu.school}**"
        if title_parts:
            line1 += "  " + "·".join(title_parts)
        if edu.start_date or edu.end_date:
            line1 += f"，{edu.start_date}-{edu.end_date}"
        lines.append(line1)
        details = []
        if edu.major:
            details.append(edu.major)
        if edu.gpa:
            details.append(f"专业成绩：{edu.gpa}")
        if edu.courses:
            details.append("主修课程：" + "、".join(f"《{c}》" for c in edu.courses))
        if edu.honors:
            details.append("曾获荣誉：" + "、".join(edu.honors))
        if details:
            lines.append("；".join(details))
        lines.append("")

    # Separator + Experience
    lines.append("---")
    lines.append("## 实习经历")
    lines.append("")
    for exp in parsed.experience:
        header = f"**{exp.company}**"
        if exp.role:
            header += f"  {exp.role}"
        if exp.start_date or exp.end_date:
            header += f"  {exp.start_date}-{exp.end_date}"
        lines.append(header)
        lines.append("")
        for i, item in enumerate(exp.items, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    # Separator + Skills
    lines.append("---")
    lines.append("## 相关技能")
    lines.append("")
    skill_order = ["工作技能", "数据技能", "AI技能", "语言能力"]
    for i, key in enumerate(skill_order, 1):
        val = parsed.skills.get(key, "")
        lines.append(f"{i}. **{key}**：{val}")

    return "\n".join(lines).strip() + "\n"
