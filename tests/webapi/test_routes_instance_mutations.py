from __future__ import annotations

import time

import pytest
import yaml

from llm_cli.core import jobs as jobs_module
from llm_cli.core.lifecycle import LifecycleError, LifecycleRecord, write_running
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.routes import instance as instance_routes


@pytest.fixture(autouse=True)
def reset_jobs():
    jobs_module._reset_for_tests()


@pytest.fixture
def seed_config(webapi_repo):
    repo_root = webapi_repo["repo_root"]
    runtime_id = "inst-rt"

    runtime_dir = repo_root / "runtimes" / runtime_id
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "id": runtime_id,
                "display_name": runtime_id,
                "kind": "official",
                "accepts_formats": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for script_name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (runtime_dir / script_name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    config_id = "inst-cfg"
    config_doc = {
        "id": config_id,
        "runtime": runtime_id,
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    }
    (webapi_repo["configs_dir"] / f"{config_id}.yaml").write_text(
        yaml.safe_dump(config_doc, sort_keys=False),
        encoding="utf-8",
    )
    return config_id


@pytest.mark.webapi
def test_start_instance_returns_job_id(test_client, seed_config, monkeypatch):
    fake_id = "start-job"

    monkeypatch.setattr(
        "llm_cli.webapi.routes.instance.jobs_module.registry",
        lambda: type(
            "R",
            (),
            {"start_async": lambda self, **kw: fake_id},
        )(),
    )
    r = test_client.post(
        "/api/instance/start",
        headers={"Host": "testserver"},
        json={"config_id": seed_config, "mode": "background"},
    )
    assert r.status_code == 200
    assert r.json() == {"job_id": fake_id}


@pytest.mark.webapi
def test_start_instance_when_already_running(test_client, webapi_repo, seed_config, monkeypatch):
    settings = resolve_settings()
    state_root = settings.data_root
    write_running(
        state_root,
        LifecycleRecord(
            mode="background",
            config_id=seed_config,
            port=8080,
            started_at="2026-05-20T00:00:00Z",
            pid=4242,
        ),
    )
    monkeypatch.setattr("llm_cli.core.lifecycle.is_alive", lambda pid: True)

    r = test_client.post(
        "/api/instance/start",
        headers={"Host": "testserver"},
        json={"config_id": seed_config, "mode": "background"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSTANCE_ALREADY_RUNNING"


@pytest.mark.webapi
def test_start_instance_404(test_client):
    r = test_client.post(
        "/api/instance/start",
        headers={"Host": "testserver"},
        json={"config_id": "missing", "mode": "background"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CONFIG_NOT_FOUND"


@pytest.mark.webapi
def test_stop_instance_ok(test_client, monkeypatch):
    monkeypatch.setattr("llm_cli.webapi.routes.instance.lifecycle.stop_instance", lambda: None)
    r = test_client.post("/api/instance/stop", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.webapi
def test_stop_instance_refuses_foreground(test_client, webapi_repo, seed_config, monkeypatch):
    settings = resolve_settings()
    state_root = settings.data_root
    write_running(
        state_root,
        LifecycleRecord(
            mode="foreground",
            config_id=seed_config,
            port=8080,
            started_at="2026-05-20T00:00:00Z",
            pid=77777,
        ),
    )
    monkeypatch.setattr("llm_cli.core.lifecycle.is_alive", lambda pid: True)

    r = test_client.post("/api/instance/stop", headers={"Host": "testserver"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSTANCE_FOREGROUND_NOT_STOPPABLE"


@pytest.mark.webapi
def test_switch_instance_returns_job_id(test_client, seed_config, monkeypatch):
    fake_id = "switch-job"

    monkeypatch.setattr(
        "llm_cli.webapi.routes.instance.jobs_module.registry",
        lambda: type(
            "R",
            (),
            {"start_async": lambda self, **kw: fake_id},
        )(),
    )
    r = test_client.post(
        "/api/instance/switch",
        headers={"Host": "testserver"},
        json={"config_id": seed_config},
    )
    assert r.status_code == 200
    assert r.json() == {"job_id": fake_id}


@pytest.mark.webapi
def test_switch_instance_refuses_foreground(
    test_client, webapi_repo, seed_config, monkeypatch
):
    settings = resolve_settings()
    state_root = settings.data_root
    write_running(
        state_root,
        LifecycleRecord(
            mode="foreground",
            config_id=seed_config,
            port=8080,
            started_at="2026-05-20T00:00:00Z",
            pid=77777,
        ),
    )
    monkeypatch.setattr("llm_cli.core.lifecycle.is_alive", lambda pid: True)

    r = test_client.post(
        "/api/instance/switch",
        headers={"Host": "testserver"},
        json={"config_id": seed_config},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSTANCE_FOREGROUND_NOT_SWITCHABLE"


@pytest.mark.webapi
def test_switch_instance_job_failure_includes_serve_log(
    test_client, webapi_repo, seed_config, monkeypatch, tmp_path
):
    from llm_cli.core import lifecycle

    monkeypatch.setattr(jobs_module, "_jobs_dir", lambda: tmp_path)
    settings = resolve_settings()
    log_path = lifecycle.logs_dir(settings.data_root) / f"{seed_config}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("GPU OOM: cannot load 35B weights\n", encoding="utf-8")

    def fail_switch(_config_id: str) -> None:
        raise LifecycleError(
            "runtime 'inst-rt' is not installed\nserve log: /tmp/x.log"
        )

    monkeypatch.setattr(
        "llm_cli.webapi.routes.instance.lifecycle.switch_instance",
        fail_switch,
    )

    r = test_client.post(
        "/api/instance/switch",
        headers={"Host": "testserver"},
        json={"config_id": seed_config},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    j = {}
    deadline = time.time() + 5.0
    while time.time() < deadline:
        j = test_client.get(
            f"/api/jobs/{job_id}", headers={"Host": "testserver"}
        ).json()
        if j["status"] == "failed":
            break
        time.sleep(0.05)

    assert j["status"] == "failed"
    assert "not installed" in j["error"]["message"]
    log_text = (tmp_path / f"{job_id}.log").read_text()
    assert "error:" in log_text
    assert "serve log tail" in log_text
    assert "GPU OOM" in log_text


@pytest.mark.webapi
def test_serve_log_tail_reads_config_log(webapi_repo, seed_config):
    from llm_cli.core import lifecycle

    settings = resolve_settings()
    log_path = lifecycle.logs_dir(settings.data_root) / f"{seed_config}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("line one\nline two\n", encoding="utf-8")
    tail = instance_routes._serve_log_tail_lines(seed_config, max_lines=10)
    assert "line one" in tail
    assert "line two" in tail
