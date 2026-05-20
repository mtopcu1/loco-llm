"""Integration tests for `llm stop`, `llm status`, `llm logs`."""
from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from llm_cli.core.lifecycle import LifecycleRecord, logs_dir, read_running, write_running
from llm_cli.core.settings import save_settings
from llm_cli.commands import lifecycle_cmds
from llm_cli.main import app
from tests.cli_helpers import data_root_path

runner = CliRunner()


def _configure(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(data_root_path(tmp_path)), "repo_root": str(repo)})


def _state(tmp_path: Path) -> Path:
    return data_root_path(tmp_path)


def _empty_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    return repo


def test_stop_no_record_is_idempotent(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "nothing running" in result.stdout.lower()


def test_stop_background_sigterms_pid_and_clears(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="background",
            config_id="cfg-a",
            port=1,
            started_at="t",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    killed = {"pid": None, "sig": None}

    def fake_kill(pid, sig):
        killed["pid"] = pid
        killed["sig"] = sig

    with (
        patch("llm_cli.commands.lifecycle_cmds.reconcile", lambda _repo: None),
        patch("llm_cli.commands.lifecycle_cmds.os.kill", new=fake_kill),
        patch("llm_cli.commands.lifecycle_cmds._wait_pid_gone", return_value=True),
    ):
        result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    assert killed["pid"] == os.getpid()
    assert read_running(repo) is None


def test_stop_background_escalates_to_sigkill_if_pid_persists(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="background",
            config_id="cfg-a",
            port=1,
            started_at="t",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    sigs = []

    def fake_kill(pid, sig):
        sigs.append(sig)

    with (
        patch("llm_cli.commands.lifecycle_cmds.reconcile", lambda _repo: None),
        patch("llm_cli.commands.lifecycle_cmds.os.kill", new=fake_kill),
        patch(
            "llm_cli.commands.lifecycle_cmds._wait_pid_gone",
            side_effect=[False, True],
        ),
    ):
        result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    assert signal.SIGTERM in sigs
    assert lifecycle_cmds._SIGKILL in sigs


def test_stop_systemd_calls_systemctl_stop(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="systemd",
            config_id="cfg-a",
            port=1,
            started_at="t",
            unit="llm.service",
        ),
    )
    with (
        patch("llm_cli.commands.lifecycle_cmds.stop_unit") as su,
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
    ):
        result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    su.assert_called_once_with("llm.service")
    assert read_running(repo) is None


def test_status_not_running(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["status"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "not running" in result.stdout.lower()


def test_status_background_text(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="background",
            config_id="cfg-a",
            port=18080,
            started_at="2026-05-17T16:00:00Z",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    with patch("llm_cli.commands.lifecycle_cmds.reconcile", lambda _repo: None):
        result = runner.invoke(app, ["status"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "running" in result.stdout.lower()
    assert "cfg-a" in result.stdout
    assert "18080" in result.stdout
    assert str(os.getpid()) in result.stdout


def test_status_json_includes_uptime_and_pid_alive(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="background",
            config_id="cfg-a",
            port=18080,
            started_at="2026-05-17T16:00:00Z",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    with (
        patch("llm_cli.commands.lifecycle_cmds.reconcile", lambda _repo: None),
        patch("llm_cli.commands.lifecycle_cmds.is_alive", return_value=True),
    ):
        result = runner.invoke(app, ["status", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "background"
    assert payload["config_id"] == "cfg-a"
    assert payload["pid"] == os.getpid()
    assert "uptime_seconds" in payload
    assert payload["pid_alive"] is True


def test_status_systemd_text(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="systemd",
            config_id="cfg-a",
            port=18080,
            started_at="2026-05-17T16:00:00Z",
            unit="llm.service",
        ),
    )
    with (
        patch("llm_cli.commands.lifecycle_cmds.systemd_is_active", return_value=True),
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
    ):
        result = runner.invoke(app, ["status"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "running" in result.stdout.lower()
    assert "llm.service" in result.stdout
    assert "journalctl" in result.stdout.lower()


def test_logs_no_record_errors(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["logs"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "nothing running" in result.stdout.lower()


@pytest.mark.skipif(sys.platform == "win32", reason="tail is not guaranteed on Windows")
def test_logs_background_tails_last_n_lines(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    logs_dir(_state(tmp_path)).mkdir(parents=True, exist_ok=True)
    log = logs_dir(_state(tmp_path)) / "cfg-a.log"
    log.write_text("\n".join(f"line-{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="background",
            config_id="cfg-a",
            port=1,
            started_at="t",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    with patch("llm_cli.commands.lifecycle_cmds.reconcile", lambda _repo: None):
        result = runner.invoke(app, ["logs", "-n", "5"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "line-20" in result.stdout
    assert "line-16" in result.stdout
    assert "line-15" not in result.stdout


def test_logs_systemd_invokes_journalctl(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        _state(tmp_path),
        LifecycleRecord(
            mode="systemd",
            config_id="cfg-a",
            port=1,
            started_at="t",
            unit="llm.service",
        ),
    )
    with (
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
        patch("llm_cli.commands.lifecycle_cmds.subprocess.call", return_value=0) as call,
    ):
        result = runner.invoke(app, ["logs", "-n", "20"], catch_exceptions=False)
    assert result.exit_code == 0
    cmd = call.call_args[0][0]
    assert cmd[:3] == ["journalctl", "--user", "-u"]
    assert "llm.service" in cmd
    assert "-n" in cmd and "20" in cmd
