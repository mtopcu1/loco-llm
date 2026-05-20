import pytest
from fastapi.testclient import TestClient

from llm_cli.webapi.app import create_app


@pytest.mark.webapi
def test_response_carries_insecure_header_when_env_set(monkeypatch):
    monkeypatch.setenv("LLM_DASHBOARD_INSECURE", "1")
    app = create_app(allowed_hosts={"testserver", "192.168.1.50:7878"})
    client = TestClient(app)
    r = client.get("/api/health", headers={"Host": "testserver"})
    assert r.headers.get("X-LocalLLM-Insecure") == "true"


@pytest.mark.webapi
def test_response_omits_insecure_header_when_env_unset(monkeypatch):
    monkeypatch.delenv("LLM_DASHBOARD_INSECURE", raising=False)
    app = create_app(allowed_hosts={"testserver"})
    client = TestClient(app)
    r = client.get("/api/health", headers={"Host": "testserver"})
    assert "X-LocalLLM-Insecure" not in r.headers
