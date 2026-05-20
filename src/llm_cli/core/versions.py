"""Lightweight version parsing and comparison.

Avoids depending on `packaging` for a tiny subset of needs.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_RELEASE_BASE = "https://github.com/mtopcu1/loco-llm/releases/tag"
_SEMVER_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_EXPECTED_REMOTE_HOSTS = ("github.com/mtopcu1/loco-llm",)

_NUM_RE = re.compile(r"\d+")


def parse_version(raw: str) -> tuple[int, ...]:
    """Extract numeric components from a version-like string.

    Strips leading 'v' and any non-numeric suffix (e.g. '-rc1').
    Raises ValueError if no numeric components found.
    """
    text = raw.strip().lstrip("v")
    if "-" in text:
        text = text.split("-", 1)[0]
    parts = _NUM_RE.findall(text)
    if not parts:
        raise ValueError(f"no numeric components in version string: {raw!r}")
    return tuple(int(p) for p in parts)


def compare_versions(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b.

    Missing components are treated as 0, so '3.11' == '3.11.0'.
    """
    pa = parse_version(a)
    pb = parse_version(b)
    length = max(len(pa), len(pb))
    pa_padded = pa + (0,) * (length - len(pa))
    pb_padded = pb + (0,) * (length - len(pb))
    if pa_padded < pb_padded:
        return -1
    if pa_padded > pb_padded:
        return 1
    return 0


def current_cli_version() -> str:
    """Return the installed CLI package version."""
    try:
        return version("loco-llm-cli")
    except PackageNotFoundError:
        from llm_cli import __version__

        return __version__


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    update_available: bool
    release_url: str | None


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _is_git_clone(root: Path) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        _run_git(root, "rev-parse", "--is-inside-work-tree")
    except subprocess.CalledProcessError:
        return False
    return True


def _remote_matches_expected(root: Path) -> bool:
    try:
        out = _run_git(root, "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        return False
    url = out.stdout.strip()
    return any(host in url for host in _EXPECTED_REMOTE_HOSTS)


def _fetch_remote(root: Path) -> None:
    _run_git(root, "fetch", "--tags", "--prune", "origin")


def _list_semver_tags(root: Path) -> list[str]:
    out = _run_git(root, "tag", "--list", "v*")
    tags = [t for t in out.stdout.split() if _SEMVER_TAG.match(t)]

    def key(tag: str) -> tuple[int, int, int]:
        parts = tag[1:].split(".")
        return tuple(int(p) for p in parts)  # type: ignore[return-value]

    return sorted(tags, key=key)


def _latest_tag(root: Path) -> str | None:
    tags = _list_semver_tags(root)
    return tags[-1] if tags else None


def _current_state(root: Path) -> dict[str, str | None]:
    sha = _run_git(root, "rev-parse", "HEAD").stdout.strip()
    branch = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch and branch != "HEAD":
        return {"kind": "branch", "ref": branch, "sha": sha}
    try:
        tag = _run_git(root, "describe", "--tags", "--exact-match", "HEAD").stdout.strip()
        if tag:
            return {"kind": "tag", "ref": tag, "sha": sha}
    except subprocess.CalledProcessError:
        pass
    return {"kind": "detached", "ref": None, "sha": sha}


def check_for_update() -> UpdateInfo:
    """Return machine-readable update status for CLI and dashboard."""
    from llm_cli.core.scaffold import scaffold_root

    current = current_cli_version()
    try:
        root = scaffold_root()
    except RuntimeError:
        return UpdateInfo(
            current=current,
            latest=current,
            update_available=False,
            release_url=None,
        )

    if not _is_git_clone(root) or not _remote_matches_expected(root):
        return UpdateInfo(
            current=current,
            latest=current,
            update_available=False,
            release_url=None,
        )

    try:
        _fetch_remote(root)
    except subprocess.CalledProcessError:
        return UpdateInfo(
            current=current,
            latest=current,
            update_available=False,
            release_url=None,
        )

    latest_tag = _latest_tag(root)
    if latest_tag is None:
        return UpdateInfo(
            current=current,
            latest=current,
            update_available=False,
            release_url=None,
        )

    latest = latest_tag.lstrip("v")
    state = _current_state(root)
    if state["kind"] == "tag" and state["ref"] == latest_tag:
        on_latest = True
        display_current = latest
    else:
        on_latest = False
        if state["kind"] == "tag" and state["ref"]:
            display_current = str(state["ref"]).lstrip("v")
        else:
            display_current = current

    return UpdateInfo(
        current=display_current,
        latest=latest,
        update_available=not on_latest,
        release_url=f"{_RELEASE_BASE}/{latest_tag}" if not on_latest else None,
    )
