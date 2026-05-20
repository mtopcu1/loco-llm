import pytest


@pytest.mark.webapi
def test_doctor_returns_all_scopes(test_client, webapi_repo):
    del webapi_repo
    r = test_client.get("/api/doctor", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["scopes"]) >= {"default", "runtime", "dashboard"}
