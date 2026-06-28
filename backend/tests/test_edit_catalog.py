from app.services.edit_catalog import build_edit_catalog, catalog_for_prompt, match_catalog_lines_semantic


SAMPLE = """---
## 实习经历

**携程**  AI 产品  2025.12-至今

1. AI 总结卡：面向滑雪场景
2. AI 快筛：参与 PRD

---
## 相关技能

1. **工作技能**：协作
"""


def test_catalog_numbered_items():
    cat = build_edit_catalog(SAMPLE)
    numbered = [c for c in cat if c["kind"] == "numbered_item"]
    assert len(numbered) == 3


def test_catalog_for_prompt_has_text():
    cat = build_edit_catalog(SAMPLE)
    rows = catalog_for_prompt(cat)
    assert rows and "text" in rows[0]


def test_semantic_match_varied_wording():
    cat = build_edit_catalog(SAMPLE)
    hits = match_catalog_lines_semantic(
        cat,
        queries=["把滑雪那个摘要模块改成项目管理说法"],
        user_message="把滑雪那个摘要模块改成项目管理说法",
    )
    assert hits
    line_text = next(c["text"] for c in cat if c["line"] == hits[0]["line"])
    assert "总结卡" in line_text or "滑雪" in line_text
