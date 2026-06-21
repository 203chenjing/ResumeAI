"""简历导出重点加粗测试。"""
from app.services.resume_emphasis import apply_emphasis_phrases, _rule_based_phrases
from app.models.schemas import JDAnalysis

SAMPLE = """# 张三

## 教育经历

**示例大学**  本科  2023-2027

---
## 实习经历

**示例公司**  产品实习生  2025.01-2025.06

1. **需求分析**：梳理 12 条核心需求，推动 2 个版本上线，次周留存提升约 8%。
2. **数据驱动**：使用 SQL/Python 搭建看板，覆盖 5 个核心指标。

---
## 相关技能

1. **工作技能**：PRD、用户调研
2. **数据技能**：Python、SQL
3. **AI技能**：RAG、Prompt 工程
4. **语言能力**：英语 CET-6
"""


def test_apply_emphasis_skips_headers():
    md, applied = apply_emphasis_phrases(
        SAMPLE,
        ["示例大学", "留存提升约 8%", "12 条核心需求"],
    )
    assert "示例大学" not in applied
    assert "留存提升约 8%" in applied
    assert "**留存提升约 8%**" in md


def test_apply_emphasis_no_double_bold():
    md = "1. **标签**：提升约 8% 的效果。"
    md2, applied = apply_emphasis_phrases(md, ["标签", "提升约 8%"])
    assert "标签" not in applied
    assert "提升约 8%" in applied
    assert md2.count("**提升约 8%**") == 1


def test_rule_based_phrases_prefers_metrics():
    jd = JDAnalysis(keywords=["RAG", "SQL"], core_requirements=["数据分析"])
    phrases = _rule_based_phrases(SAMPLE, jd)
    assert any("8%" in p or "12" in p or "5" in p for p in phrases)
