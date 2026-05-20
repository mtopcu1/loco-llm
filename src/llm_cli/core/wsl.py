"""Convert Windows paths for WSL and invoke bash scripts in the repo context."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path, PureWindowsPath

from llm_cli.core.scaffold import scaffold_root
from llm_cli.core.settings import Settings


def is_windows() -> bool:
    return os.name == "nt"


def to_wsl_path(path: Path) -> str:
    """Best-effort POSIX path for bash inside WSL (Windows drive -> /mnt/c/...)."""
    wp = PureWindowsPath(str(path))
    # Map Windows-shaped absolutes to /mnt/<drive>/... when actually on POSIX, or
    # when `is_windows()` is True. When `os.name == "nt"` but tests patch
    # `is_windows()` to False, fall through to `resolve().as_posix()` so host
    # paths are not mis-read as DrvFs paths.
    if wp.drive and wp.is_absolute() and (is_windows() or os.name != "nt"):
        letter = wp.drive.rstrip(":").lower()
        try:
            rel = wp.relative_to(wp.anchor).as_posix()
        except ValueError:
            rel = (
                wp.as_posix()
                .split(":", 1)[-1]
                .lstrip("/\\")
                .replace("\\", "/")
            )
        if not rel or rel == ".":
            return f"/mnt/{letter}"
        return f"/mnt/{letter}/{rel}"

    resolved = path.resolve()
    if is_windows() and resolved.drive:
        letter = resolved.drive.rstrip(":").lower()
        try:
            rel = resolved.relative_to(resolved.anchor).as_posix()
        except ValueError:
            rel = (
                resolved.as_posix().split(":", 1)[-1].lstrip("/").replace("\\", "/")
            )
        if not rel or rel == ".":
            return f"/mnt/{letter}"
        return f"/mnt/{letter}/{rel}"

    return resolved.as_posix()


_PATH_ENV_KEYS = frozenset(
    {"LLM_DATA_ROOT", "LLM_REPO_ROOT", "LLM_RUNTIMES", "LLM_MODELS", "LLM_CACHE"}
)


def _llm_env(settings: Settings) -> dict[str, str]:
    return {
        "LLM_DATA_ROOT": settings.data_root.as_posix(),
        "LLM_REPO_ROOT": scaffold_root().as_posix(),
        "LLM_RUNTIMES": settings.runtimes_dir.as_posix(),
        "LLM_MODELS": settings.models_dir.as_posix(),
        "LLM_CACHE": settings.cache_dir.as_posix(),
    }


def _bash_env(settings: Settings, extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Env vars as they must appear inside bash (WSL paths on Windows)."""
    merged = _llm_env(settings)
    if extra_env:
        merged.update(extra_env)
    if not is_windows():
        return merged
    out: dict[str, str] = {}
    for key, value in merged.items():
        if key in _PATH_ENV_KEYS:
            out[key] = to_wsl_path(Path(value))
        else:
            out[key] = value
    return out


def _bash_export_prefix(env: dict[str, str]) -> str:
    """Inline exports so WSL bash sees LLM_* (Windows env is not forwarded)."""
    if not env:
        return ""
    exports = "; ".join(
        f"export {key}={shlex.quote(value)}" for key, value in sorted(env.items())
    )
    return f"{exports}; "


def run_repo_bash(
    settings: Settings,
    script_posix_relpath: str,
    script_args: list[str] | None = None,
    *,
    extra_env: dict[str, str] | None = None,
) -> int:
    """Run a bash script relative to scaffold_root with LLM_* env injected.

    On Windows, uses `wsl -e bash -lc ...`. On POSIX, uses `bash -lc ...`.
    Returns the child process exit code.
    """
    script_args = script_args or []
    repo_wsl = to_wsl_path(scaffold_root())
    script_wsl = f"{repo_wsl}/{script_posix_relpath.lstrip('/')}"
    args_str = " ".join(shlex.quote(a) for a in script_args)
    cmd_tail = f"bash {shlex.quote(script_wsl)}" + (f" {args_str}" if args_str else "")
    bash_env = _bash_env(settings, extra_env)
    inner = (
        "set -euo pipefail; "
        f"{_bash_export_prefix(bash_env)}"
        f"cd {shlex.quote(repo_wsl)}; "
        f"{cmd_tail}"
    )
    bash = ["bash", "-lc", inner]
    if is_windows():
        full_cmd = ["wsl", "-e", *bash]
    else:
        full_cmd = bash
    return int(subprocess.call(full_cmd, env=os.environ.copy()))


def run_runtime_bash(
    settings: Settings,
    runtime_path: Path,
    script_name: str,
    script_args: list[str] | None = None,
    *,
    extra_env: dict[str, str] | None = None,
) -> int:
    """Run a script inside a runtime asset directory (scaffold or user layer)."""
    script_args = script_args or []
    rt_wsl = to_wsl_path(runtime_path)
    script_wsl = f"{rt_wsl}/{script_name.lstrip('/')}"
    args_str = " ".join(shlex.quote(a) for a in script_args)
    cmd_tail = f"bash {shlex.quote(script_wsl)}" + (f" {args_str}" if args_str else "")
    bash_env = _bash_env(settings, extra_env)
    inner = (
        "set -euo pipefail; "
        f"{_bash_export_prefix(bash_env)}"
        f"cd {shlex.quote(rt_wsl)}; "
        f"{cmd_tail}"
    )
    bash = ["bash", "-lc", inner]
    if is_windows():
        full_cmd = ["wsl", "-e", *bash]
    else:
        full_cmd = bash
    return int(subprocess.call(full_cmd, env=os.environ.copy()))
