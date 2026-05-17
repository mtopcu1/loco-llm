"""Minimal Hugging Face Hub metadata client (read-only, public API)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_BASE = "https://huggingface.co/api/models"


class HFApiError(RuntimeError):
    """Wraps HTTP / network failures from the public HF API."""


@dataclass(frozen=True)
class HFSibling:
    rfilename: str
    size: int | None
    lfs_sha256: str | None


@dataclass(frozen=True)
class HFRepoInfo:
    repo: str
    revision: str
    sha: str
    license: str | None
    siblings: list[HFSibling]


def _request(url: str, *, token: str | None) -> bytes:
    headers = {"Accept": "application/json", "User-Agent": "localllm-cli/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read()
    except HTTPError as exc:
        raise HFApiError(f"HF API HTTP {exc.code} for {url}: {exc.reason}") from exc
    except URLError as exc:
        raise HFApiError(f"HF API network error for {url}: {exc.reason}") from exc


def fetch_repo_revision(repo: str, revision: str = "main") -> HFRepoInfo:
    """Fetch repo metadata for `<repo>@<revision>`; HFApiError on failure."""
    url = f"{_BASE}/{repo}/revision/{revision}"
    token = os.environ.get("HF_TOKEN")
    raw = _request(url, token=token)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HFApiError(f"HF API returned non-JSON for {url}: {exc}") from exc

    card = payload.get("cardData") or {}
    license_ = card.get("license") if isinstance(card, dict) else None
    siblings_raw = payload.get("siblings") or []
    siblings: list[HFSibling] = []
    for s in siblings_raw:
        if not isinstance(s, dict):
            continue
        lfs = s.get("lfs") if isinstance(s.get("lfs"), dict) else None
        siblings.append(
            HFSibling(
                rfilename=str(s.get("rfilename", "")),
                size=int(s["size"]) if isinstance(s.get("size"), int) else None,
                lfs_sha256=str(lfs["sha256"]) if lfs and "sha256" in lfs else None,
            )
        )
    return HFRepoInfo(
        repo=str(payload.get("id", repo)),
        revision=revision,
        sha=str(payload.get("sha", "")),
        license=str(license_) if isinstance(license_, str) else None,
        siblings=siblings,
    )
