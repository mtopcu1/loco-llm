import pytest
from fastapi.testclient import TestClient

from llm_cli.webapi.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    # Force an empty dist_dir so SPA fallback yields 503 for /
    monkeypatch.setattr("llm_cli.webapi.app._dist_dir", lambda: tmp_path / "empty-dist")
    app = create_app(allowed_hosts={"testserver"})
    return TestClient(app)


@pytest.mark.webapi
def test_health_returns_ok(client):
    r = client.get("/api/health", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.webapi
def test_version_returns_cli_version(client):
    r = client.get("/api/version", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert "cli_version" in body
    assert isinstance(body["cli_version"], str)


@pytest.mark.webapi
def test_spa_not_built_yields_503(client):
    r = client.get("/", headers={"Host": "testserver"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "DASHBOARD_NOT_BUILT"
