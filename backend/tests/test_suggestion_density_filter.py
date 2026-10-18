"""建议密度过滤：稀疏简历不删内容，密集简历最多删两条。

回归背景：`_filter_suggestions_by_density` 曾因漏 import `assess_density`
在「一键改稿」主链路上抛 NameError，测试没覆盖到就会整条链路 500。
"""
from app.models.schemas import Suggestion
from app.services.suggestion_engine import _filter_suggestions_by_density


def _delete(sid: str) -> Suggestion:
    return Suggestion(
        id=sid,
        section="experience",
        type="delete",
        original_text="要删除的内容",
        suggested_text="",
        reason="精简",
    )


def _wording(sid: str) -> Suggestion:
    return Suggestion(
        id=sid,
        section="experience",
        type="wording",
        original_text="原文",
        suggested_text="改后",
        reason="更贴 JD",
    )


def test_sparse_resume_drops_delete_suggestions():
    sparse_md = "# 张三\n\n## 实习经历\n\n1. 做了点事。\n"
    result = _filter_suggestions_by_density([_delete("d1"), _delete("d2")], sparse_md)
    assert result == []


def test_dense_resume_keeps_at_most_two_deletes():
    dense_md = "## 实习经历\n\n" + "产出明确、可量化的项目描述。" * 200
    suggestions = [_delete("d1"), _delete("d2"), _delete("d3")]
    result = _filter_suggestions_by_density(suggestions, dense_md)
    assert [s.id for s in result] == ["d1", "d2"]


def test_non_delete_suggestions_are_never_dropped():
    sparse_md = "# 张三\n\n## 实习经历\n\n1. 做了点事。\n"
    result = _filter_suggestions_by_density([_wording("w1"), _wording("w2")], sparse_md)
    assert [s.id for s in result] == ["w1", "w2"]
