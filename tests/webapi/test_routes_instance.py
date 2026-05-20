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
    import yaml

    settings = resolve_settings()
    rt_dir = webapi_repo["repo_root"] / "runtimes" / "stub-runtime"
    rt_dir.mkdir(parents=True, exist_ok=True)
    (rt_dir / "manifest.yaml").write_text(
        "id: stub-runtime\ndisplay_name: stub\naccepts_formats: []\n",
        encoding="utf-8",
    )
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt_dir / name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (webapi_repo["configs_dir"] / "cfg-1.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "cfg-1",
                "runtime": "stub-runtime",
                "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    write_running(
        settings.data_root,
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


@pytest.mark.webapi
def test_instance_metrics_stream_not_running(test_client, webapi_repo):
    del webapi_repo
    r = test_client.get(
        "/api/instance/metrics/stream",
        headers={"Host": "testserver", "Accept": "text/event-stream"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSTANCE_NOT_RUNNING"


@pytest.mark.webapi
def test_instance_metrics_stream_no_metrics_event(test_client, webapi_repo, monkeypatch):
    from llm_cli.core.registry import RuntimeRecord

    rt_dir = webapi_repo["repo_root"] / "runtimes" / "stub-runtime"
    monkeypatch.setattr(
        "llm_cli.core.lifecycle_status.current",
        lambda: {
            "running": True,
            "config_id": "cfg-stub",
            "runtime_id": "stub-runtime",
            "port": 8000,
            "mode": "background",
        },
    )
    monkeypatch.setattr(
        "llm_cli.core.registry.get_runtime_merged",
        lambda rid: RuntimeRecord(
            id="stub-runtime",
            path=rt_dir,
            manifest={"id": "stub-runtime", "metrics": None},
        )
        if rid == "stub-runtime"
        else None,
    )

    with test_client.stream(
        "GET",
        "/api/instance/metrics/stream",
        headers={"Host": "testserver", "Accept": "text/event-stream"},
        timeout=2.0,
    ) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text(chunk_size=1))
        assert "no_metrics" in body
