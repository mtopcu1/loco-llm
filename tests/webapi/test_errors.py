import pytest


@pytest.mark.webapi
def test_api_error_response_shape(client):
    r = client.get("/raise/RUNTIME_NOT_INSTALLED")
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "RUNTIME_NOT_INSTALLED"
    assert body["error"]["message"] == "raised RUNTIME_NOT_INSTALLED"
    assert body["error"]["details"] == {"code_name": "RUNTIME_NOT_INSTALLED"}
    assert "request_id" in body


@pytest.mark.webapi
def test_unhandled_exception_returns_500_without_stack(client):
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "synthetic" not in body["error"]["message"]
    assert "request_id" in body
