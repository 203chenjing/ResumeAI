from app.prompts.role_lens import build_role_lens_section, infer_role_bucket


def test_infer_from_archetype_field():
    assert infer_role_bucket("项目管理", "软件项目经理") == "项目管理"
    assert infer_role_bucket("AI产品经理", "AI产品实习生") == "AI产品经理"


def test_infer_fuzzy_archetype():
    assert infer_role_bucket("软件产品经理", "") == "软件产品经理"


def test_build_role_lens_contains_reframe():
    text = build_role_lens_section(
        {
            "role": "项目管理",
            "archetype": "项目管理",
            "core_requirements": ["风险意识", "跨部门协调"],
            "ranking": {"核心匹配": ["推进项目交付"]},
        }
    )
    assert "叙事镜头" in text
    assert "项目管理" in text
    assert "里程碑" in text or "交付" in text
