"""简历内容密度评估（对齐 SKILL 一页 A4 目标）。"""

# 按当前 A4 模板（正文 8.5pt / 左右 48pt）实测标定：约 2940 字填满一页
SPARSE_THRESHOLD = 1900   # 低于此值底部易明显留白
IDEAL_MIN = 2200
IDEAL_MAX = 2800
DENSE_THRESHOLD = 2940    # 高于此值易溢出到第 2 页


def count_chars(md: str) -> int:
    return len(md.strip())


def assess_density(md: str) -> dict:
    chars = count_chars(md)
    if chars < SPARSE_THRESHOLD:
        return {
            "char_count": chars,
            "status": "sparse",
            "message": (
                f"目前约 {chars} 字，内容偏少，一页底部容易留白。"
                "建议补充经历细节，或谨慎采纳删减类建议。"
            ),
        }
    if chars > DENSE_THRESHOLD:
        return {
            "char_count": chars,
            "status": "dense",
            "message": (
                f"目前约 {chars} 字，偏多，可能挤不下单页。"
                "建议合并或压缩优先级较低的内容。"
            ),
        }
    if chars < IDEAL_MIN:
        return {
            "char_count": chars,
            "status": "light",
            "message": f"目前约 {chars} 字，略少。定稿前可再补 1–2 处与岗位相关的细节。",
        }
    return {
        "char_count": chars,
        "status": "ok",
        "message": f"目前约 {chars} 字，长度适合一页 PDF。",
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
