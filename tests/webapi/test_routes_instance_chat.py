from __future__ import annotations

import pytest
import yaml


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
    config_id = "inst-cfg"
    (webapi_repo["configs_dir"] / f"{config_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": config_id,
                "runtime": runtime_id,
                "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return config_id


@pytest.mark.webapi
def test_chat_readiness_when_not_running(test_client):
    r = test_client.get("/api/instance/chat/readiness", headers={"Host": "testserver"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSTANCE_NOT_RUNNING"


@pytest.mark.webapi
def test_chat_when_not_running(test_client):
    r = test_client.post(
        "/api/instance/chat",
        headers={"Host": "testserver"},
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSTANCE_NOT_RUNNING"


@pytest.mark.webapi
def test_chat_readiness_ok(test_client, webapi_repo, seed_config, monkeypatch):
    from llm_cli.core.lifecycle import LifecycleRecord, write_running
    from llm_cli.core.settings import resolve_settings

    settings = resolve_settings()
    write_running(
        settings.data_root,
        LifecycleRecord(
            mode="background",
            config_id=seed_config,
            port=18080,
            started_at="2026-05-20T00:00:00Z",
            pid=4242,
        ),
    )

    class FakeResp:
        status_code = 200

        def json(self):
            return {"data": [{"id": "test-model"}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return FakeResp()

    monkeypatch.setattr(
        "llm_cli.webapi.routes.instance_chat.httpx.AsyncClient",
        lambda **kw: FakeClient(),
    )

    r = test_client.get(
        "/api/instance/chat/readiness?timeout_sec=5&interval_sec=0.5",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["config_id"] == seed_config
    assert body["models"] == ["test-model"]
