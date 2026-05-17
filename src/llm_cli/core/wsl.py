"""Convert Windows paths for WSL and invoke bash scripts in the repo context."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path, PureWindowsPath


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


def run_repo_bash(
    repo: Path,
    script_posix_relpath: str,
    script_args: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> int:
    """Run a bash script relative to repo. Sources `.llm-env` when present.

    On Windows, uses `wsl -e bash -lc ...`. On POSIX, uses `bash -lc ...`.
    Returns the child process exit code.
    """
    script_args = script_args or []
    repo_wsl = to_wsl_path(repo)
    script_wsl = f"{repo_wsl}/{script_posix_relpath.lstrip('/')}"
    args_str = " ".join(shlex.quote(a) for a in script_args)
    cmd_tail = f"bash {shlex.quote(script_wsl)}" + (f" {args_str}" if args_str else "")
    inner = (
        "set -euo pipefail; "
        f"cd {shlex.quote(repo_wsl)}; "
        "if [ -f .llm-env ]; then set -a && . ./.llm-env && set +a; fi; "
        f"{cmd_tail}"
    )
    bash = ["bash", "-lc", inner]
    if is_windows():
        full_cmd = ["wsl", "-e", *bash]
    else:
        full_cmd = bash
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return int(subprocess.call(full_cmd, env=merged))
