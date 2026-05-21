"""Resolve scaffold and dev repo paths from user settings."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.scaffold import configured_repo_root, scaffold_root as _scaffold_root
from llm_cli.core.settings import (
    MissingSettingError,
    load_settings,
    resolve,
)


class RepoRootMissing(RuntimeError):
    """Raised when a configured repo_root is missing or invalid."""


def scaffold_root() -> Path:
    """Return the effective read-only asset root (managed scaffold or dev checkout)."""
    return _scaffold_root()


def repo_root() -> Path:
    """Return the dev checkout path when repo_root is configured in settings.

    For distributed installs, use scaffold_root() instead. This helper exists
    for editable installs and migration scripts that still reference repo_root.
    """
    dev = configured_repo_root()
    if dev is not None:
        return dev
    try:
        resolved = resolve(load_settings())
    except MissingSettingError as exc:
        raise RepoRootMissing(str(exc)) from exc
    if resolved.repo_root is not None and resolved.repo_root.is_dir():
        return resolved.repo_root.resolve()
    raise RepoRootMissing(
        "repo_root is not configured; distributed installs use the managed scaffold. "
        "For development, run `loco settings edit repo_root` to point at your clone."
    )
