"""Thin subprocess wrapper used by detection and check helpers."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    found: bool  # False if executable not on PATH
    timed_out: bool  # True if killed by timeout


def run_command(
    cmd: Sequence[str],
    *,
    timeout_sec: float = 10.0,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> CommandResult:
    """Run a command, capture its output, never raise on failure.

    Returns CommandResult with `found=False` if the executable isn't on PATH
    and `timed_out=True` if the process was killed by the timeout.
    """
    full_env: dict[str, str] = dict(os.environ)
    if env:
        full_env.update(env)

    try:
        completed = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=full_env,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(exit_code=-1, stdout="", stderr="", found=False, timed_out=False)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            exit_code=-1,
            stdout=exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "",
            stderr=exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "",
            found=True,
            timed_out=True,
        )

    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        found=True,
        timed_out=False,
    )
