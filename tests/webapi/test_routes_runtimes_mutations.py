from __future__ import annotations

import pytest
import yaml

from llm_cli.core.lifecycle import LifecycleRecord, write_running
from llm_cli.core.runtime_install import default_build_param_tokens
from llm_cli.core.settings import resolve_settings


@pytest.fixture
def seed_runtime(webapi_repo):
    repo_root = webapi_repo["repo_root"]

    def _seed(runtime_id: str, *, kind: str = "official") -> None:
        runtime_dir = repo_root / "runtimes" / runtime_id
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "manifest.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": runtime_id,
                    "display_name": runtime_id,
                    "kind": kind,
                    "accepts_formats": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        for script_name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (runtime_dir / script_name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    return _seed


@pytest.mark.webapi
def test_install_runtime_returns_job_id(test_client, seed_runtime, monkeypatch):
    seed_runtime("stub-rt")
    fake_id = "abc123"

    def fake_start(**kwargs):
        assert kwargs["kind"] == "runtime_install"
        assert kwargs["context"]["runtime_id"] == "stub-rt"
        assert callable(kwargs["coro_factory"])
        return fake_id

    monkeypatch.setattr(
        "llm_cli.webapi.routes.runtimes.jobs_module.registry",
        lambda: type("R", (), {"start_async": lambda self, **kw: fake_start(**kw)})(),
    )
    r = test_client.post("/api/runtimes/stub-rt/install", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"job_id": fake_id}


@pytest.mark.webapi
def test_install_vllm_default_build_params():
    assert default_build_param_tokens("vllm") == [
        "vllm_version=0.21.0",
        "pip_extra=cuda",
    ]


@pytest.mark.webapi
def test_install_runtime_404(test_client):
    r = test_client.post("/api/runtimes/missing/install", headers={"Host": "testserver"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RUNTIME_NOT_FOUND"


@pytest.mark.webapi
def test_rebuild_runtime_returns_job_id(test_client, seed_runtime, monkeypatch):
    seed_runtime("stub-rt")
    fake_id = "rebuild99"

    monkeypatch.setattr(
        "llm_cli.webapi.routes.runtimes.jobs_module.registry",
        lambda: type(
            "R",
            (),
            {"start_async": lambda self, **kw: fake_id},
        )(),
    )
    r = test_client.post(
        "/api/runtimes/stub-rt/rebuild?reset=true",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    assert r.json() == {"job_id": fake_id}


@pytest.mark.webapi
def test_uninstall_runtime_ok(test_client, seed_runtime):
    seed_runtime("stub-rt")
    r = test_client.delete("/api/runtimes/stub-rt", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.webapi
def test_uninstall_runtime_refuses_when_in_use(
    test_client, seed_runtime, webapi_repo, monkeypatch
):
    runtime_id = "in-use-rt"
    config_id = "cfg-using-rt"
    seed_runtime(runtime_id)

    repo_root = webapi_repo["repo_root"]
    config_doc = {
        "id": config_id,
        "runtime": runtime_id,
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    }
    (webapi_repo["configs_dir"] / f"{config_id}.yaml").write_text(
        yaml.safe_dump(config_doc, sort_keys=False),
        encoding="utf-8",
    )

    settings = resolve_settings()
    state_root = settings.data_root
    write_running(
        state_root,
        LifecycleRecord(
            mode="background",
            config_id=config_id,
            port=8080,
            started_at="2026-05-20T00:00:00Z",
            pid=99999,
        ),
    )

    import llm_cli.core.lifecycle as lifecycle_mod

    monkeypatch.setattr(lifecycle_mod, "is_alive", lambda pid: True)

    r = test_client.delete(f"/api/runtimes/{runtime_id}", headers={"Host": "testserver"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "RUNTIME_IN_USE"
