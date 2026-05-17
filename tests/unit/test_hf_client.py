from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from llm_cli.core.hf_client import (
    HFApiError,
    HFRepoInfo,
    HFSibling,
    fetch_repo_revision,
)


_FAKE_PAYLOAD = {
    "id": "Qwen/Qwen2.5-7B-Instruct",
    "sha": "deadbeef",
    "cardData": {"license": "apache-2.0"},
    "siblings": [
        {
            "rfilename": "config.json",
            "size": 612,
            "lfs": None,
        },
        {
            "rfilename": "model-00001-of-00004.safetensors",
            "size": 4900000000,
            "lfs": {"sha256": "abc123", "size": 4900000000},
        },
    ],
}


def _fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    resp.status = 200
    return resp


def test_fetch_repo_revision_parses_payload():
    with patch("llm_cli.core.hf_client.urlopen", return_value=_fake_response(_FAKE_PAYLOAD)):
        info = fetch_repo_revision("Qwen/Qwen2.5-7B-Instruct", revision="main")
    assert isinstance(info, HFRepoInfo)
    assert info.repo == "Qwen/Qwen2.5-7B-Instruct"
    assert info.revision == "main"
    assert info.sha == "deadbeef"
    assert info.license == "apache-2.0"
    by_name = {s.rfilename: s for s in info.siblings}
    assert by_name["config.json"].lfs_sha256 is None
    assert by_name["config.json"].size == 612
    assert by_name["model-00001-of-00004.safetensors"].lfs_sha256 == "abc123"


def test_fetch_includes_authorization_when_hf_token_env(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        return _fake_response(_FAKE_PAYLOAD)

    monkeypatch.setenv("HF_TOKEN", "secret123")
    with patch("llm_cli.core.hf_client.urlopen", side_effect=fake_urlopen):
        fetch_repo_revision("Qwen/Qwen2.5-7B-Instruct", revision="main")
    assert captured["auth"] == "Bearer secret123"


def test_fetch_404_raises_hf_api_error(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)

    def boom(req, timeout):
        from urllib.error import HTTPError
        raise HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    with patch("llm_cli.core.hf_client.urlopen", side_effect=boom):
        with pytest.raises(HFApiError, match="HTTP 404"):
            fetch_repo_revision("nope/nope")


def test_fetch_network_error_raises_hf_api_error(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    from urllib.error import URLError

    with patch("llm_cli.core.hf_client.urlopen", side_effect=URLError("offline")):
        with pytest.raises(HFApiError, match="network error"):
            fetch_repo_revision("Qwen/Qwen2.5-7B-Instruct")
