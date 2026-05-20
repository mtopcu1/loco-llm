from __future__ import annotations

import pytest


@pytest.mark.webapi
def test_put_setting_valid(test_client, webapi_repo, tmp_path):
    del webapi_repo
    new_root = tmp_path / "custom-data"
    r = test_client.put(
        "/api/settings/data_root",
        headers={"Host": "testserver"},
        json={"value": str(new_root)},
    )
    assert r.status_code == 200
    assert r.json()["stored"]["data_root"] == str(new_root)
    assert r.json()["resolved"]["data_root"] == str(new_root)


@pytest.mark.webapi
def test_put_setting_unknown_key(test_client):
    r = test_client.put(
        "/api/settings/not_a_key",
        headers={"Host": "testserver"},
        json={"value": "x"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SETTINGS_UNKNOWN_KEY"


@pytest.mark.webapi
def test_put_setting_validation_failed(test_client):
    r = test_client.put(
        "/api/settings/data_root",
        headers={"Host": "testserver"},
        json={"value": "   "},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "SETTINGS_VALIDATION_FAILED"


@pytest.mark.webapi
def test_put_setting_clear_optional_key(test_client, webapi_repo):
    repo = webapi_repo["repo_root"]
    r = test_client.put(
        "/api/settings/repo_root",
        headers={"Host": "testserver"},
        json={"value": str(repo)},
    )
    assert r.status_code == 200
    assert r.json()["stored"]["repo_root"] == str(repo)

    r = test_client.put(
        "/api/settings/repo_root",
        headers={"Host": "testserver"},
        json={"value": None},
    )
    assert r.status_code == 200
    assert "repo_root" not in r.json()["stored"]


@pytest.mark.webapi
def test_put_setting_cannot_clear_required(test_client):
    r = test_client.put(
        "/api/settings/data_root",
        headers={"Host": "testserver"},
        json={"value": None},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "SETTINGS_VALIDATION_FAILED"
