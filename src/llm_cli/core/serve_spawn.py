"""Build bash commands, probe ports, wait for readiness, spawn fg/bg processes."""
from __future__ import annotations

import socket


def _bash_single_quote(host_path: str) -> str:
    """Single-quote *host_path* for POSIX `sh` / bash (WSL), escaping embedded `'`."""
    return "'" + host_path.replace("'", "'\"'\"'") + "'"


def port_in_use(host: str, port: int) -> bool:
    """True if attempting to bind (host, port) raises EADDRINUSE.

    Avoids ``SO_REUSEADDR`` on the probe: on Windows, reuse can allow a second
    bind while another socket is already listening, which would false-negative
    this check.
    """
    s = socket.socket()
    try:
        try:
            s.bind((host, port))
        except OSError:
            return True
        return False
    finally:
        s.close()


def build_serve_inner(repo_posix: str, script_posix_relpath: str) -> str:
    """Inner bash for serve.sh — cd into repo and exec the script.

    The final `exec` is essential: it makes the script's PID become the
    server's PID, so `kill -TERM <pid>` from `llm stop` reaches the server
    directly with no intermediate bash wrapper.
    """
    rel = script_posix_relpath.lstrip("/")
    return (
        "set -euo pipefail; "
        f"cd {_bash_single_quote(repo_posix)}; "
        f"exec bash {_bash_single_quote(rel)}"
    )
