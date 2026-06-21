from app.services import user_memory as um


def test_load_default_memory(tmp_user_memory):
    mem = um.load_memory("client_a")
    assert mem["knowledge_base_md"] == ""
    assert mem["preferences"]["review_policy"] == "accept_safe"


def test_save_and_load_roundtrip(tmp_user_memory):
    um.save_memory("client_b", {"knowledge_base_md": "STAR 案例", "notes": "秋招"})
    mem = um.load_memory("client_b")
    assert mem["knowledge_base_md"] == "STAR 案例"
    assert mem["notes"] == "秋招"


def test_merge_preferences(tmp_user_memory):
    applied = um.merge_preferences("c1", {"writing_style": "简洁", "review_policy": "manual"})
    assert applied["writing_style"] == "简洁"
    mem = um.load_memory("c1")
    assert mem["preferences"]["prefer_accept_safe"] is False
