from app.models.schemas import Suggestion
from app.services.resume_list_format import (
    ensure_experience_item_format,
    normalize_experience_markdown,
)
from app.services.suggestion_engine import _normalize_experience_suggestions


def test_bold_title_from_colon():
    raw = "1. AI 总结卡交付：在泛意图场景下拆解模块范围并推动按期交付"
    out = ensure_experience_item_format(raw)
    assert out.startswith("1. **AI 总结卡交付**：")


def test_preserve_number_from_reference():
    raw = "参与模块范围拆解并协调评审对齐"
    ref = "2. 快筛模块：原内容"
    out = ensure_experience_item_format(raw, reference=ref)
    assert out.startswith("2. **")


def test_normalize_markdown_block():
    md = """# 姓名

---
## 实习经历

**公司**  岗位  2025.01-2025.06

1. 项目 A：完成交付
2. 项目 B：推动上线

---
## 相关技能

1. **工作技能**：协作
"""
    out = normalize_experience_markdown(md)
    assert "1. **项目 A**：完成交付" in out
    assert "2. **项目 B**：推动上线" in out


def test_normalize_experience_suggestions():
    sug = Suggestion(
        id="s1",
        section="experience",
        type="star",
        original_text="1. 旧标题：旧内容",
        suggested_text="1. 新标题：新内容",
        reason="test",
        jd_match_points=["x"],
    )
    out = _normalize_experience_suggestions([sug])
    assert out[0].suggested_text.startswith("1. **新标题**：")
