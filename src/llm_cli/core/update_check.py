"""Fetch latest CLI and scaffold versions from PyPI and GitHub."""
from __future__ import annotations

import httpx

from llm_cli.core.versions import compare_versions

PYPI_JSON_URL = "https://pypi.org/pypi/loco-llm-cli/json"
GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/mtopcu1/local-llm-scaffold/releases/latest"
)


def fetch_pypi_latest_version() -> str:
    """Return the latest loco-llm-cli version from PyPI."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(PYPI_JSON_URL)
        resp.raise_for_status()
        data = resp.json()
    version = data.get("info", {}).get("version")
    if not version:
        raise ValueError("PyPI response missing info.version")
    return str(version)


def fetch_github_latest_release() -> dict:
    """Return GitHub /releases/latest payload (tag_name, body, assets, ...)."""
    headers = {"Accept": "application/vnd.github+json"}
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(GITHUB_LATEST_RELEASE_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("GitHub release response is not an object")
    return data


def parse_version_tag(tag: str) -> str:
    """Strip a leading ``v`` so the tag compares with ``__version__``."""
    return tag.strip().lstrip("v")


def is_behind(current: str, latest: str) -> bool:
    """True if *current* is strictly older than *latest*."""
    return compare_versions(current, latest) < 0
