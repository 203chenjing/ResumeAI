"""面试准备包测试。"""
from app.services.interview_prep import build_prep_pack


def test_build_prep_pack():
    pack = build_prep_pack(
        jd_text="Python 后端 Redis MySQL",
        company="测试公司",
        role="后端工程师",
        knowledge_md="### 项目\n- **行动**：使用 Python 开发 API",
    )
    assert pack["company"] == "测试公司"
    assert "hr" in pack["questions"]
    assert len(pack["questions"]["technical"]) >= 1
