"""POSIX process stop helpers shared by lifecycle, serve, and CLI."""
from __future__ import annotations

import os
import signal
import time

from llm_cli.core.lifecycle import is_alive

_SIGKILL = int(getattr(signal, "SIGKILL", 9))


def wait_pid_gone(pid: int, timeout_s: float = 10.0, poll_s: float = 0.2) -> bool:
    """Poll until ``is_alive(pid)`` is false or timeout elapses."""
    deadline = time.monotonic() + timeout_s
    while is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)
    return True


def stop_background_pid(pid: int) -> None:
    """Send SIGTERM, wait, then SIGKILL if the process is still alive."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if not wait_pid_gone(pid, timeout_s=10.0):
        try:
            os.kill(pid, _SIGKILL)
        except ProcessLookupError:
            return
        wait_pid_gone(pid, timeout_s=2.0)
