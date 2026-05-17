"""Tests for serve_spawn: bash builders, port probe, readiness loop."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock

import pytest

from llm_cli.core.serve_spawn import (
    build_serve_inner,
    port_in_use,
    spawn_background,
    spawn_foreground,
    wait_for_ready,
)


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


def test_build_serve_inner_uses_exec_and_cd() -> None:
    inner = build_serve_inner(
        repo_posix="/repo",
        script_posix_relpath="runtimes/stub/serve.sh",
    )
    assert inner.startswith("set -euo pipefail; ")
    assert "cd '/repo'" in inner
    assert inner.endswith("exec bash 'runtimes/stub/serve.sh'")


def test_build_serve_inner_quotes_paths_with_spaces() -> None:
    inner = build_serve_inner(
        repo_posix="/home/me/a repo",
        script_posix_relpath="runtimes/x/serve.sh",
    )
    assert "'/home/me/a repo'" in inner


def test_wait_for_ready_succeeds_on_first_call() -> None:
    calls = {"n": 0}

    def probe() -> bool:
        calls["n"] += 1
        return True

    ok = wait_for_ready(probe, timeout_s=5.0, poll_s=0.01)
    assert ok is True
    assert calls["n"] == 1


def test_wait_for_ready_succeeds_after_some_failures() -> None:
    calls = {"n": 0}

    def probe() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    ok = wait_for_ready(probe, timeout_s=5.0, poll_s=0.01)
    assert ok is True
    assert calls["n"] == 3


def test_wait_for_ready_times_out() -> None:
    def probe() -> bool:
        return False

    ok = wait_for_ready(probe, timeout_s=0.05, poll_s=0.02)
    assert ok is False


def test_spawn_background_runs_nohup_and_returns_pid() -> None:
    runner = MagicMock()
    runner.return_value = MagicMock(stdout="12345\n", returncode=0)
    pid = spawn_background(
        inner="set -e; exec bash 'runtimes/x/serve.sh'",
        log_path="/repo/state/logs/x.log",
        env={"LLM_DATA_ROOT": "/root"},
        runner=runner,
    )
    assert pid == 12345
    assert runner.call_count == 1
    cmd = runner.call_args[0][0]
    assert cmd[0] == "bash"
    assert cmd[1] == "-lc"
    bash_script = cmd[2]
    assert "nohup" in bash_script
    assert ">> '/repo/state/logs/x.log'" in bash_script
    assert "echo \"$!\"" in bash_script
    passed_env = runner.call_args[1]["env"]
    assert passed_env["LLM_DATA_ROOT"] == "/root"


def test_spawn_background_raises_when_stdout_has_no_pid() -> None:
    runner = MagicMock()
    runner.return_value = MagicMock(stdout="", returncode=0)
    with pytest.raises(RuntimeError):
        spawn_background(
            inner="x",
            log_path="/repo/log",
            env={},
            runner=runner,
        )


def test_spawn_background_raises_on_nonzero_exit() -> None:
    runner = MagicMock()
    runner.return_value = MagicMock(stdout="999\n", returncode=2)
    with pytest.raises(RuntimeError):
        spawn_background(
            inner="x",
            log_path="/repo/log",
            env={},
            runner=runner,
        )


def test_spawn_foreground_invokes_runner_and_returns_pid_and_exit_code() -> None:
    """Foreground returns (pid, exit_code) — on_started fires once PID is known."""
    started = {"pid": None}

    def on_started(pid: int) -> None:
        started["pid"] = pid

    class FakePopen:
        def __init__(self, cmd: list, *, env: dict) -> None:
            self.cmd = cmd
            self.env = env
            self.pid = 4242

        def wait(self) -> int:
            return 0

    def runner(cmd: list, *, env: dict) -> FakePopen:
        return FakePopen(cmd, env=env)

    pid, code = spawn_foreground(
        inner="x",
        env={"LLM_DATA_ROOT": "/r"},
        on_started=on_started,
        runner=runner,
    )
    assert pid == 4242
    assert code == 0
    assert started["pid"] == 4242


def test_spawn_foreground_propagates_nonzero_exit() -> None:
    class FakePopen:
        pid = 99

        def __init__(self, cmd: list, *, env: dict) -> None:
            pass

        def wait(self) -> int:
            return 7

    _pid, code = spawn_foreground(
        inner="x",
        env={},
        on_started=lambda _pid: None,
        runner=lambda cmd, *, env: FakePopen(cmd, env=env),
    )
    assert code == 7
