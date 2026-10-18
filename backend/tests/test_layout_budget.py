"""一页预算：字数/页数估算与结构计数。"""
from app.services.layout_budget import (
    capacity_pct,
    estimate_pages,
    experience_items,
    layout_metrics,
    skill_items,
)

# 真实场景：解析把「项目 → 子要点」拍平成平级编号
FLATTENED = """# 张三

## 实习经历

**示例公司**  产品实习生  2025.01-2025.06

1. **项目一｜大搜改版**：主导结果页摘要模块
2. **1）体验拆解**：拆成三个模块
3. **2）AI 摘要**：设计 Prompt 约束
4. **3）AI 快筛**：标签投放
5. **4）AI 亮点**：种草文案

**示例公司二**  产品助理  2024.01-2024.06

1. **项目二｜工单重构**：重排审批节点
2. **1）调研**：访谈 14 人

## 相关技能

1. **工作技能**：PRD、竞品分析
2. **数据技能**：SQL
3. **AI技能**：Prompt
4. **语言能力**：英语
"""

DEMOTED = """# 张三

## 实习经历

**示例公司**  产品实习生  2025.01-2025.06

1. **项目一｜大搜改版**：主导结果页摘要模块
1）**体验拆解**：拆成三个模块
2）**AI 摘要**：设计 Prompt 约束
3）**AI 快筛**：标签投放
4）**AI 亮点**：种草文案

**示例公司二**  产品助理  2024.01-2024.06

1. **项目二｜工单重构**：重排审批节点
1）**调研**：访谈 14 人

## 相关技能

1. **工作技能**：PRD、竞品分析
2. **数据技能**：SQL
3. **AI技能**：Prompt
4. **语言能力**：英语
"""


def test_flattened_structure_counts_5_items():
    """拍平后会误判为 5 条，正是用户被规则拦住的原因。"""
    assert experience_items(FLATTENED) == 5


def test_demoted_structure_counts_1_item():
    """还原层级后，每段经历只有 1 条顶层编号。"""
    assert experience_items(DEMOTED) == 1


def test_skill_items_counted():
    assert skill_items(DEMOTED) == 4


def test_metrics_shape():
    metrics = layout_metrics(DEMOTED)
    assert metrics["experience_items"] == 1
    assert metrics["experience_limit"] == 5
    assert metrics["skill_items"] == 4
    assert metrics["skill_limit"] == 4
    assert 0 <= metrics["capacity_pct"] <= 100


def test_page_estimate_calibration():
    # 实测：~2000 字 1 页，~3050 字 2 页
    assert estimate_pages(2000) == 1
    assert estimate_pages(3050) == 2
    assert estimate_pages(0) == 0


def test_capacity_pct_capped():
    assert capacity_pct(0) == 0
    assert capacity_pct(10_000) == 100
