"""Tests for PyPI/GitHub update version checks."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from llm_cli.core.update_check import (
    fetch_github_latest_release,
    fetch_pypi_latest_version,
    is_behind,
    parse_version_tag,
)


def test_parse_version_tag_strips_v() -> None:
    assert parse_version_tag("v0.4.1") == "0.4.1"
    assert parse_version_tag("0.4.1") == "0.4.1"


def test_is_behind() -> None:
    assert is_behind("0.3.0", "0.4.0") is True
    assert is_behind("0.4.0", "0.4.0") is False
    assert is_behind("0.5.0", "0.4.0") is False


def test_fetch_pypi_latest_version() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"info": {"version": "0.4.1"}}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("llm_cli.core.update_check.httpx.Client", return_value=mock_client):
        assert fetch_pypi_latest_version() == "0.4.1"
    mock_client.get.assert_called_once()


def test_fetch_github_latest_release() -> None:
    payload = {
        "tag_name": "v0.4.1",
        "body": "changelog",
        "assets": [{"name": "scaffold-v0.4.1.tar.gz"}],
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("llm_cli.core.update_check.httpx.Client", return_value=mock_client):
        out = fetch_github_latest_release()
    assert out["tag_name"] == "v0.4.1"
    assert out["assets"][0]["name"] == "scaffold-v0.4.1.tar.gz"


def test_fetch_pypi_missing_version_raises() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"info": {}}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("llm_cli.core.update_check.httpx.Client", return_value=mock_client):
        with pytest.raises(ValueError, match="info.version"):
            fetch_pypi_latest_version()
