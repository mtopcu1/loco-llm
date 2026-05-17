"""Build bash commands, probe ports, wait for readiness, spawn fg/bg processes."""
from __future__ import annotations

import socket


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
