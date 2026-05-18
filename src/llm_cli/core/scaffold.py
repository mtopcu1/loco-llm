"""Scaffold and user asset directory resolution."""
from __future__ import annotations

import os
from pathlib import Path

from llm_cli.core.settings import Settings, load_settings


def xdg_data_home() -> Path:
    """Return XDG_DATA_HOME or ~/.local/share."""
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser()
    return Path.home() / ".local" / "share"


def default_scaffold_dir() -> Path:
    return xdg_data_home() / "localllm" / "scaffold"


def scaffold_dir() -> Path:
    """Managed scaffold directory (tarball extract target)."""
    override = os.environ.get("LLM_SCAFFOLD_DIR")
    if override:
        return Path(override).expanduser()
    return default_scaffold_dir()


def configured_repo_root() -> Path | None:
    """Dev override: explicit repo_root from settings, if set and valid."""
    values = load_settings()
    raw = values.get("repo_root")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path.resolve() if path.is_dir() else None


def scaffold_root() -> Path:
    """Read-only official assets: dev checkout or managed scaffold dir."""
    dev = configured_repo_root()
    if dev is not None:
        return dev
    return scaffold_dir().resolve()


def user_assets_root(settings: Settings) -> Path:
    return settings.data_root / "user"


def user_runtimes_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "runtimes"


def user_configs_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "configs"


def user_benchmarks_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "benchmarks"


def read_scaffold_version() -> str | None:
    """Return the tag in .scaffold-version, or None if missing."""
    path = scaffold_dir() / ".scaffold-version"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None
