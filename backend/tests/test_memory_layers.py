"""六层记忆架构单元测试。"""
from app.services import auto_dream, memdir, session_memory, working_memory
from app.models.schemas import Session


def test_memdir_ensure_and_sync(tmp_path, monkeypatch):
    monkeypatch.setattr(memdir, "DATA_ROOT", tmp_path / "memdir")
    memdir.ensure_memdir("client_x")
    memdir.sync_from_user_memory(
        "client_x",
        {
            "knowledge_base_md": "曾在某厂负责推荐系统",
            "preferences": {"writing_style": "量化 STAR"},
            "notes": "秋招目标",
        },
    )
    index = memdir.read_index("client_x")
    assert "knowledge-base.md" in index
    assert "量化 STAR" in memdir.read_topic("client_x", "preferences")


def test_working_memory_tracks_steps():
    sess = Session(session_id="s1")
    wm = working_memory.update_working_memory(
        sess,
        goal="完成匹配",
        current_step="analyze_jd",
        completed_step="analyze_jd",
        checkpoint={"match_score": 70},
    )
    assert wm["goal"] == "完成匹配"
    assert "analyze_jd" in wm["completed_steps"]
    ctx = working_memory.working_memory_context(sess)
    assert "L3 工作记忆" in ctx


def test_session_memory_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(session_memory, "DATA_ROOT", tmp_path / "session_memory")
    sess = Session(session_id="sess_abc")
    sess.status = "matched"
    sess.chat_history = [
        __import__("app.models.schemas", fromlist=["ChatMessage"]).ChatMessage(role="user", content="帮我优化项目经历"),
        __import__("app.models.schemas", fromlist=["ChatMessage"]).ChatMessage(role="assistant", content="好的"),
    ] * 7
    summary = session_memory.build_rolling_summary(sess)
    session_memory.write_summary(sess.session_id, summary)
    assert "会话摘要" in session_memory.read_summary(sess.session_id)


def test_autodream_force_consolidate(tmp_path, monkeypatch):
    monkeypatch.setattr(memdir, "DATA_ROOT", tmp_path / "memdir")
    monkeypatch.setattr(auto_dream, "SESSION_MEMORY_ROOT", tmp_path / "session_memory")
    memdir.ensure_memdir("dream_client")
    memdir.save_dream_state("dream_client", {"sessions_since_consolidation": 10})
    result = auto_dream.consolidate("dream_client", force=True)
    assert result["success"] is True
    status = auto_dream.dream_status("dream_client")
    assert status["sessions_since_consolidation"] == 0
