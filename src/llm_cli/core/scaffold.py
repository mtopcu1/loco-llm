"""Resolve loco-llm install root (git) and data home (user-owned tree)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from llm_cli.core.settings import Settings, default_data_home, load_settings, resolve


def data_home() -> Path:
    """User data root: config.yaml, configs/, models/, builds, state/."""
    try:
        return resolve(load_settings()).data_root
    except Exception:
        return default_data_home()


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


def install_root() -> Path:
    """Git checkout with CLI source and upstream runtime/benchmark recipes."""
    for key in ("LOCO_INSTALL", "LOCO_LLM_HOME"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
    dev = configured_repo_root()
    if dev is not None:
        return dev
    nested = data_home() / "install"
    if (nested / ".git").is_dir():
        return nested.resolve()
    top = _module_git_toplevel()
    if top is not None:
        return top
    raise RuntimeError(
        "could not resolve install root; set LOCO_INSTALL, run install.sh, "
        "or set repo_root for development"
    )


def scaffold_root() -> Path:
    """Alias for install_root (historical name)."""
    return install_root()


def configs_dir(settings: Settings) -> Path:
    """Launch configs live only under the data home (seeded at install)."""
    return settings.data_root / "configs"


def user_assets_root(settings: Settings) -> Path:
    return settings.data_root / "user"


def user_runtimes_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "runtimes"


def user_configs_dir(settings: Settings) -> Path:
    """Deprecated alias — use configs_dir()."""
    return configs_dir(settings)


def user_benchmarks_dir(settings: Settings) -> Path:
    return user_assets_root(settings) / "benchmarks"


def seed_configs_from_install(
    *,
    install: Path | None = None,
    dest: Path | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Copy example configs from install root into data home (skip existing)."""
    src_root = install or install_root()
    dst_root = dest or configs_dir(resolve(load_settings()))
    src = src_root / "configs"
    if not src.is_dir():
        return []
    dst_root.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for path in sorted(src.glob("*.yaml")):
        target = dst_root / path.name
        if target.exists() and not overwrite:
            continue
        shutil.copy2(path, target)
        copied.append(target)
    return copied
