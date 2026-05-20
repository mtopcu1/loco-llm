from __future__ import annotations

import pytest

from llm_cli.core import lifecycle
from llm_cli.core.settings import resolve_settings


def _state_root():
    settings = resolve_settings()
    return lifecycle.state_root(settings)


@pytest.mark.webapi
def test_history_list_supports_limit_and_filters(test_client, webapi_repo):
    del webapi_repo
    root = _state_root()
    lifecycle.append_history(root, {"action": "start", "config_id": "cfg-a", "ts": "2026-05-20T00:00:00Z"})
    lifecycle.append_history(root, {"action": "stop", "config_id": "cfg-b", "ts": "2026-05-20T00:01:00Z"})

    r = test_client.get("/api/history?limit=1&action=stop", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert len(body["items"]) == 1
    assert body["items"][0]["action"] == "stop"


@pytest.mark.webapi
def test_history_stream_emits_existing_entries_in_once_mode(test_client, webapi_repo):
    del webapi_repo
    root = _state_root()
    lifecycle.append_history(root, {"action": "config-create", "id": "cfg1", "ts": "2026-05-20T00:00:00Z"})

    with test_client.stream(
        "GET",
        "/api/history/stream?once=true",
        headers={"Host": "testserver", "Accept": "text/event-stream"},
        timeout=2.0,
    ) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text(chunk_size=1))
        assert "config-create" in body
