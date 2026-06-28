from app.models.schemas import Suggestion
from app.services.suggestion_engine import _filter_noop_suggestions


def test_filter_noop_suggestion_by_unchanged_text():
    suggestions = [
        Suggestion(
            id="s1",
            section="experience",
            type="wording",
            original_text="负责产品培训、内网推广与用户反馈收集。",
            suggested_text="负责产品培训、内网推广与用户反馈收集。",
            reason="原文已体现主动推进和持续学习，无需修改。",
            jd_match_points=["主动性"],
        ),
        Suggestion(
            id="s2",
            section="experience",
            type="star",
            original_text="负责数据分析。",
            suggested_text="分析用户行为数据，输出转化优化建议。",
            reason="补充行动和产出。",
            jd_match_points=["数据分析"],
        ),
    ]

    filtered = _filter_noop_suggestions(suggestions)

    assert [s.id for s in filtered] == ["s2"]


def test_filter_noop_suggestion_by_reason():
    suggestion = Suggestion(
        id="s1",
        section="experience",
        type="keyword",
        original_text="参与问答上线与运营推广。",
        suggested_text="参与问答上线与运营推广。",
        reason="这条不用再改。",
        jd_match_points=["运营推广"],
    )

    assert _filter_noop_suggestions([suggestion]) == []
