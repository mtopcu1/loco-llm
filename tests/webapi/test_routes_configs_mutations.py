from __future__ import annotations

import pytest
import yaml

from llm_cli.core.lifecycle import LifecycleRecord, write_running
from llm_cli.core.settings import resolve_settings


@pytest.fixture
def seed_runtime(webapi_repo):
    repo_root = webapi_repo["repo_root"]

    def _seed(runtime_id: str = "rt-mut") -> str:
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
        return runtime_id

    return _seed


def _valid_config(config_id: str, runtime_id: str = "rt-mut") -> dict:
    return {
        "id": config_id,
        "runtime": runtime_id,
        "serve": {"host": "127.0.0.1", "port": 9001, "params": {}},
        "readiness": {"timeout_seconds": 600},
    }


@pytest.mark.webapi
def test_create_config(test_client, seed_runtime):
    seed_runtime()
    body = _valid_config("new-cfg")
    r = test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)
    assert r.status_code == 200
    assert r.json()["id"] == "new-cfg"


@pytest.mark.webapi
def test_create_config_conflict(test_client, seed_runtime):
    seed_runtime()
    body = _valid_config("dup-cfg")
    r1 = test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)
    assert r1.status_code == 200
    r2 = test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "CONFIG_ALREADY_EXISTS"


@pytest.mark.webapi
def test_create_config_validation_failure(test_client, seed_runtime):
    seed_runtime()
    body = _valid_config("bad-cfg")
    del body["serve"]["port"]
    r = test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "CONFIG_INVALID"
    assert r.json()["error"]["details"]["errors"]


@pytest.mark.webapi
def test_update_config(test_client, seed_runtime):
    seed_runtime()
    body = _valid_config("upd-cfg")
    test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)
    body["serve"]["port"] = 9002
    r = test_client.put("/api/configs/upd-cfg", headers={"Host": "testserver"}, json=body)
    assert r.status_code == 200
    assert r.json()["data"]["serve"]["port"] == 9002


@pytest.mark.webapi
def test_delete_config(test_client, seed_runtime):
    seed_runtime()
    body = _valid_config("del-cfg")
    test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)
    r = test_client.delete("/api/configs/del-cfg", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.webapi
def test_delete_config_refuses_when_in_use(test_client, seed_runtime, webapi_repo, monkeypatch):
    seed_runtime()
    body = _valid_config("live-cfg")
    test_client.post("/api/configs", headers={"Host": "testserver"}, json=body)

    settings = resolve_settings()
    state_root = settings.data_root
    write_running(
        state_root,
        LifecycleRecord(
            mode="background",
            config_id="live-cfg",
            port=9001,
            started_at="2026-05-20T00:00:00Z",
            pid=88888,
        ),
    )
    import llm_cli.core.lifecycle as lifecycle_mod

    monkeypatch.setattr(lifecycle_mod, "is_alive", lambda pid: True)

    r = test_client.delete("/api/configs/live-cfg", headers={"Host": "testserver"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFIG_IN_USE"
