import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_cli.webapi.middleware import (
    HostHeaderMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.add_middleware(SecurityHeadersMiddleware)
    a.add_middleware(HostHeaderMiddleware, allowed_hosts={"127.0.0.1:7878", "localhost:7878"})
    a.add_middleware(RequestIDMiddleware)

    @a.get("/")
    def _root():
        return {"ok": True}

    return a


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.mark.webapi
def test_request_id_header_present(client):
    r = client.get("/", headers={"Host": "127.0.0.1:7878"})
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
    assert len(r.headers["X-Request-ID"]) >= 16


@pytest.mark.webapi
def test_host_header_allowed(client):
    r = client.get("/", headers={"Host": "127.0.0.1:7878"})
    assert r.status_code == 200


@pytest.mark.webapi
def test_host_header_rejected_returns_421(client):
    r = client.get("/", headers={"Host": "evil.example.com"})
    assert r.status_code == 421


@pytest.mark.webapi
def test_security_headers_present(client):
    r = client.get("/", headers={"Host": "127.0.0.1:7878"})
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
