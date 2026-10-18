from app.services.suggestion_anchor import anchor_original_text, find_line_range


SAMPLE = """---
## 实习经历

**携程**  产品实习生  2025.12-至今

1. 大搜结果页 AI 化·AI 总结卡：面向滑雪场景参与产品设计
2. 大搜结果页 AI 化·AI 快筛：参与快筛模块 PRD 撰写

---
## 相关技能
"""


def test_exact_match():
    line = "1. 大搜结果页 AI 化·AI 总结卡：面向滑雪场景参与产品设计"
    anchored, lr = anchor_original_text(SAMPLE, line)
    assert anchored == line
    assert lr[0] > 0


def test_fuzzy_title_match():
    anchored, lr = anchor_original_text(SAMPLE, "AI 总结卡：改成项目管理视角")
    assert "总结卡" in anchored
    assert anchored.startswith("1.")
    assert lr[0] > 0


def test_find_line_range():
    # 建议文本可能带旧编号（这里 1.），简历里是 2.：应按内容定位，而不是按编号失配返回 [0, 0]
    line = "1. 大搜结果页 AI 化·AI 快筛：参与快筛模块 PRD 撰写"
    line_range = find_line_range(SAMPLE, line)
    assert line_range == [7, 7]
    assert "快筛" in SAMPLE.splitlines()[line_range[0] - 1]
