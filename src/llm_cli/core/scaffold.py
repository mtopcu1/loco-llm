"""Resolve LOCO_LLM_HOME — the git checkout that is the install root."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from llm_cli.core.settings import Settings, load_settings


def _module_git_toplevel() -> Path | None:
    """Best-effort: git toplevel of the directory containing this module."""
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.run(
            ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    top = out.stdout.strip()
    return Path(top).resolve() if top else None


def configured_repo_root() -> Path | None:
    """Dev override: explicit repo_root from settings, if set and valid."""
    values = load_settings()
    raw = values.get("repo_root")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path.resolve() if path.is_dir() else None


def scaffold_root() -> Path:
    """Return the git checkout root (LOCO_LLM_HOME, dev override, or git toplevel)."""
    env = os.environ.get("LOCO_LLM_HOME")
    if env:
        return Path(env).expanduser().resolve()
    dev = configured_repo_root()
    if dev is not None:
        return dev
    top = _module_git_toplevel()
    if top is not None:
        return top
    raise RuntimeError(
        "could not resolve scaffold root; set LOCO_LLM_HOME or run from a git checkout"
    )


def user_assets_root(settings: Settings) -> Path:
    return settings.data_root / "user"


def user_runtimes_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "runtimes"


def user_configs_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "configs"


def user_benchmarks_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "benchmarks"
