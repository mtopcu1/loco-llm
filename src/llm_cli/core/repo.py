"""Resolve the LocalLLM repo root from user settings."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.settings import (
    MissingSettingError,
    load_settings,
    resolve,
)


class RepoRootMissing(RuntimeError):
    """Raised when the configured repo_root is missing or invalid."""


def repo_root() -> Path:
    """Return the absolute path of the LocalLLM repo as configured."""
    try:
        resolved = resolve(load_settings())
    except MissingSettingError as exc:
        raise RepoRootMissing(str(exc)) from exc
    if not resolved.repo_root.is_dir():
        raise RepoRootMissing(
            f"repo_root points at {resolved.repo_root}, which is not a directory; "
            "run `llm settings edit repo_root` to fix"
        )
    return resolved.repo_root.resolve()
