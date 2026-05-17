"""Tests for serve_spawn: bash builders, port probe, readiness loop."""
from __future__ import annotations

import socket

from llm_cli.core.serve_spawn import port_in_use


def test_port_in_use_false_on_free_port() -> None:
    # Find a free port by binding to :0 then closing.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert port_in_use("127.0.0.1", port) is False


def test_port_in_use_true_when_bound() -> None:
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen()
    try:
        assert port_in_use("127.0.0.1", port) is True
    finally:
        s.close()
