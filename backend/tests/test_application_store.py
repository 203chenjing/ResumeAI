from app.services.application_store import create_application, delete_application, list_applications, _save


def test_delete_application(tmp_path, monkeypatch):
    from app.services import application_store

    monkeypatch.setattr(application_store, "DATA_DIR", tmp_path)
    cid = "delete_test"
    app = create_application(cid, {"company": "测试公司", "role": "产品实习生"})
    assert len(list_applications(cid)) == 1

    removed = delete_application(cid, app["id"])
    assert removed["company"] == "测试公司"
    assert list_applications(cid) == []
