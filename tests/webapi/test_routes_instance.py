from __future__ import annotations

import pytest

from llm_cli.core.lifecycle import LifecycleRecord, write_running
from llm_cli.core.settings import resolve_settings


@pytest.mark.webapi
def test_instance_returns_not_running_when_no_state(test_client):
    r = test_client.get("/api/instance", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"running": False}


@pytest.mark.webapi
def test_instance_stream_yields_initial_snapshot(test_client):
    with test_client.stream(
        "GET",
        "/api/instance/stream?once=true",
        headers={"Host": "testserver", "Accept": "text/event-stream"},
        timeout=2.0,
    ) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text(chunk_size=1))
        assert "data:" in body


@pytest.mark.webapi
def test_instance_logs_stream_returns_error_when_not_running(test_client):
    with test_client.stream(
        "GET",
        "/api/instance/logs/stream",
        headers={"Host": "testserver", "Accept": "text/event-stream"},
        timeout=2.0,
    ) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text(chunk_size=1))
        assert "INSTANCE_NOT_RUNNING" in body


@pytest.mark.webapi
def test_instance_endpoint_returns_running_payload(test_client, webapi_repo):
    settings = resolve_settings()
    state_root = webapi_repo["repo_root"] if settings.repo_root else settings.data_root
    write_running(
        state_root,
        LifecycleRecord(
            mode="background",
            config_id="cfg-1",
            port=8080,
            started_at="2026-05-20T00:00:00Z",
            pid=12345,
            log_path="state/logs/cfg-1.log",
        ),
    )
    r = test_client.get("/api/instance", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json()["running"] is True
    assert r.json()["config_id"] == "cfg-1"
