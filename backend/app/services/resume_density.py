"""简历内容密度评估（对齐 SKILL 一页 A4 目标）。"""

# SKILL：约 1700–2200 汉字；<1500 易底部空白；>2400 易溢出 2 页
SPARSE_THRESHOLD = 1500
IDEAL_MIN = 1700
IDEAL_MAX = 2200
DENSE_THRESHOLD = 2400


def count_chars(md: str) -> int:
    return len(md.strip())


def assess_density(md: str) -> dict:
    chars = count_chars(md)
    if chars < SPARSE_THRESHOLD:
        return {
            "char_count": chars,
            "status": "sparse",
            "message": (
                f"当前约 {chars} 字，低于单页饱满下限（建议 ≥{IDEAL_MIN} 字）。"
                "接受过多删减后底部易空白，请优先补充经历细节或拒绝 delete 类建议。"
            ),
        }
    if chars > DENSE_THRESHOLD:
        return {
            "char_count": chars,
            "status": "dense",
            "message": (
                f"当前约 {chars} 字，超过单页安全上限（建议 ≤{IDEAL_MAX} 字）。"
                "继续扩写可能变成 2 页，请合并或压缩低优先级内容。"
            ),
        }
    if chars < IDEAL_MIN:
        return {
            "char_count": chars,
            "status": "light",
            "message": f"当前约 {chars} 字，略偏少，定稿前建议补充 1–2 处 JD 相关细节。",
        }
    return {
        "char_count": chars,
        "status": "ok",
        "message": f"当前约 {chars} 字，密度适合 A4 单页。",
    }


def density_hint_for_prompt(md: str) -> str:
    d = assess_density(md)
    if d["status"] == "sparse":
        return (
            f"当前简历约 {d['char_count']} 字，**严重偏少**。"
            "禁止生成 delete 类建议；优先 star/keyword 类**扩写**真实细节。"
        )
    if d["status"] in ("light", "ok"):
        return (
            f"当前简历约 {d['char_count']} 字，目标定稿 {IDEAL_MIN}–{IDEAL_MAX} 字。"
            "delete 类建议最多 1 条，且必须有等量扩写建议补偿密度。"
        )
    return (
        f"当前简历约 {d['char_count']} 字，偏多。"
        "可适度 wording 压缩，但禁止连续多条 delete；每删一处须在别处保留 JD 证据。"
    )
