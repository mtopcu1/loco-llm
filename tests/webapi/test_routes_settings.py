import pytest


@pytest.mark.webapi
def test_get_settings_returns_stored_resolved_registry(test_client, webapi_repo):
    del webapi_repo
    r = test_client.get("/api/settings", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert "stored" in body
    assert "resolved" in body
    assert "registry" in body
    assert any(item["key"] == "data_root" for item in body["registry"])
