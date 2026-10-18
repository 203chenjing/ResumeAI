"""从知识库生成简历服务测试。"""
from __future__ import annotations

import pytest

from app.models.schemas import JDAnalysis, Session
from app.services import resume_from_knowledge as rfk


GOLDEN_RESUME = """# 张三

手机：13800000000 | 邮箱：a@b.com | 上海
求职意向：产品实习生

## 教育经历

**复旦大学**  计算机学院 · 本科  2022.09-2026.06

---
## 实习经历

**示例公司**  产品实习  2025.01-2025.06

1. **需求分析**：完成 3 个功能迭代。

---
## 相关技能

1. **工作技能**：需求分析
2. **数据技能**：SQL
3. **AI技能**：Prompt
4. **语言能力**：英语六级
"""

KB = """## 实习/项目素材
### 示例公司 · 产品实习 · 2025.01-2025.06
- 完成 3 个功能迭代，DAU 提升 10%
"""


@pytest.mark.asyncio
async def test_build_resume_from_knowledge_updates_session(monkeypatch):
    async def fake_chat_text(_sys, _user, **kwargs):
        return GOLDEN_RESUME

    async def fake_match(_md, _jd):
        from app.models.schemas import MatchResult

        return MatchResult(overall_score=78)

    async def fake_suggestions(*args, **kwargs):
        from app.models.schemas import Suggestion

        return [Suggestion(
            id="s1",
            section="experience",
            type="wording",
            original_text="old",
            suggested_text="new",
            reason="test",
            status="pending",
        )], {}

    monkeypatch.setattr(rfk.client, "chat_text", fake_chat_text)
    monkeypatch.setattr(rfk, "analyze_match", fake_match)
    monkeypatch.setattr(rfk, "generate_suggestions", fake_suggestions)

    sess = Session(
        session_id="kb-test",
        jd_analysis=JDAnalysis(role="产品实习生", company="示例公司"),
        current_resume_md="# 旧简历",
    )
    result = await rfk.build_resume_from_knowledge(sess, knowledge_base=KB)
    assert "张三" in result["markdown"]
    assert sess.current_resume_md.startswith("# 张三")
    assert result["suggestions_count"] == 1
    assert sess.knowledge_base_md.strip() == KB.strip()


@pytest.mark.asyncio
async def test_build_resume_empty_kb_raises(monkeypatch):
    # 隔离 L4 记忆回退：否则默认 client 会读到仓库内 memory/ 的素材并真打 LLM
    monkeypatch.setattr(rfk, "load_memory", lambda _cid="default": {})
    sess = Session(
        session_id="kb-empty",
        jd_analysis=JDAnalysis(role="产品"),
    )
    with pytest.raises(ValueError, match="知识库为空"):
        await rfk.build_resume_from_knowledge(sess, knowledge_base="")


@pytest.mark.asyncio
async def test_build_resume_no_jd_raises():
    sess = Session(session_id="no-jd", knowledge_base_md=KB)
    with pytest.raises(ValueError, match="岗位分析"):
        await rfk.build_resume_from_knowledge(sess)
