from __future__ import annotations

import pytest

from llm_cli.core import jobs as jobs_module
from llm_cli.core.versions import UpdateInfo
from llm_cli.webapi.routes import update as update_routes


@pytest.fixture(autouse=True)
def reset_jobs():
    jobs_module._reset_for_tests()


@pytest.fixture(autouse=True)
def clear_update_cache():
    update_routes._CACHE = None
    yield
    update_routes._CACHE = None


@pytest.mark.webapi
def test_update_check_returns_info(test_client, monkeypatch):
    monkeypatch.setattr(
        "llm_cli.core.versions.check_for_update",
        lambda: UpdateInfo(
            current="1.0.0",
            latest="1.2.0",
            update_available=True,
            release_url="https://example.com/release",
        ),
    )
    r = test_client.get("/api/update/check", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert body["current"] == "1.0.0"
    assert body["latest"] == "1.2.0"
    assert body["update_available"] is True
    assert body["release_url"] == "https://example.com/release"


@pytest.mark.webapi
def test_update_check_uses_cache(test_client, monkeypatch):
    calls = {"n": 0}

    def fake_check():
        calls["n"] += 1
        return UpdateInfo(
            current="1.0.0",
            latest="1.0.0",
            update_available=False,
            release_url=None,
        )

    monkeypatch.setattr("llm_cli.core.versions.check_for_update", fake_check)
    test_client.get("/api/update/check", headers={"Host": "testserver"})
    test_client.get("/api/update/check", headers={"Host": "testserver"})
    assert calls["n"] == 1


@pytest.mark.webapi
def test_trigger_update_starts_job(test_client, webapi_repo, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs_module, "_jobs_dir", lambda: tmp_path)
    captured: dict = {}

    def fake_start(*, kind, context, argv, env=None, cwd=None):
        captured["kind"] = kind
        captured["argv"] = argv
        captured["context"] = context
        return "job-1"

    monkeypatch.setattr(jobs_module.registry(), "start_subprocess", fake_start)
    r = test_client.post("/api/update?restart_dashboard=true", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json()["job_id"] == "job-1"
    assert captured["kind"] == "update"
    assert "update" in captured["argv"]
    assert "--restart" in captured["argv"]
