"""Integration tests for `llm serve`, `llm switch`. Uses runner injection — no real bash."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.lifecycle import LifecycleRecord, read_running, write_running
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _configure(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


def _make_repo(root: Path, port: int = 18080) -> Path:
    repo = root / "repo"
    repo.mkdir()
    rt = repo / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text("id: rt-a\n", encoding="utf-8")
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    md = repo / "models" / "md-a"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text("id: md-a\n", encoding="utf-8")
    (md / "pull.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (repo / "configs").mkdir()
    (repo / "configs" / "cfg-a.yaml").write_text(
        f"id: cfg-a\nruntime: rt-a\nmodel: md-a\nserve:\n  host: 127.0.0.1\n  port: {port}\n",
        encoding="utf-8",
    )
    return repo


def test_serve_background_writes_running_json_and_calls_spawn(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18091)
    _configure(tmp_path, repo)
    with (
        patch("llm_cli.commands.serve.spawn_background", return_value=5555) as sb,
        patch("llm_cli.commands.serve.wait_for_ready", return_value=True),
        patch("llm_cli.commands.serve.port_in_use", return_value=False),
    ):
        result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    sb.assert_called_once()
    rec = read_running(repo)
    assert rec is not None
    assert rec.mode == "background"
    assert rec.config_id == "cfg-a"
    assert rec.pid == 5555
    assert rec.port == 18091


def test_serve_fails_when_port_in_use(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18092)
    _configure(tmp_path, repo)
    with patch("llm_cli.commands.serve.port_in_use", return_value=True):
        result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "already in use" in result.stdout.lower()


def test_serve_fails_when_unknown_config(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["serve", "nope"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "unknown config" in result.stdout.lower()


def test_serve_readiness_timeout_kills_child_and_clears_state(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18093)
    _configure(tmp_path, repo)
    killed = {"called": False}

    def fake_kill(pid, sig):
        killed["called"] = True

    with (
        patch("llm_cli.commands.serve.spawn_background", return_value=8888),
        patch("llm_cli.commands.serve.wait_for_ready", return_value=False),
        patch("llm_cli.commands.serve.port_in_use", return_value=False),
        patch("llm_cli.commands.serve.os.kill", new=fake_kill),
    ):
        result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert (
        "timed out" in result.stdout.lower() or "did not become ready" in result.stdout.lower()
    )
    assert killed["called"] is True
    assert read_running(repo) is None


def test_serve_foreground_writes_running_and_clears_on_exit(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18094)
    _configure(tmp_path, repo)

    def fake_spawn_fg(*, inner, env, on_started, **kw):
        on_started(7777)
        assert read_running(repo).pid == 7777
        return 7777, 0

    with (
        patch("llm_cli.commands.serve.spawn_foreground", new=fake_spawn_fg),
        patch("llm_cli.commands.serve.port_in_use", return_value=False),
    ):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--foreground"], catch_exceptions=False
        )
    assert result.exit_code == 0
    assert read_running(repo) is None


def test_serve_systemd_rewrites_unit_and_writes_running(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18095)
    _configure(tmp_path, repo)
    with (
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
        patch("llm_cli.commands.serve.write_if_different", return_value=True) as wid,
        patch("llm_cli.commands.serve.daemon_reload") as dr,
        patch("llm_cli.commands.serve.restart_unit") as ru,
        patch("llm_cli.commands.serve.wait_for_ready", return_value=True),
        patch("llm_cli.commands.serve.systemd_is_active", return_value=True),
        patch("llm_cli.commands.serve.port_in_use", return_value=False),
    ):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--systemd"], catch_exceptions=False
        )
    assert result.exit_code == 0, result.stdout
    wid.assert_called_once()
    dr.assert_called_once()
    ru.assert_called_once_with("llm.service")
    rec = read_running(repo)
    assert rec is not None
    assert rec.mode == "systemd"
    assert rec.unit == "llm.service"
    assert rec.config_id == "cfg-a"


def test_serve_systemd_skips_daemon_reload_when_unit_unchanged(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18096)
    _configure(tmp_path, repo)
    with (
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
        patch("llm_cli.commands.serve.write_if_different", return_value=False),
        patch("llm_cli.commands.serve.daemon_reload") as dr,
        patch("llm_cli.commands.serve.restart_unit") as ru,
        patch("llm_cli.commands.serve.wait_for_ready", return_value=True),
        patch("llm_cli.commands.serve.systemd_is_active", return_value=True),
        patch("llm_cli.commands.serve.port_in_use", return_value=False),
    ):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--systemd"], catch_exceptions=False
        )
    assert result.exit_code == 0
    dr.assert_not_called()
    ru.assert_called_once()


def test_foreground_from_supervisor_does_not_touch_running_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18097)
    _configure(tmp_path, repo)
    pre = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=18097,
        started_at="t",
        unit="llm.service",
    )
    write_running(repo, pre)

    def fake_spawn_fg(*, inner, env, on_started, **kw):
        on_started(1234)
        return 1234, 0

    with (
        patch("llm_cli.commands.serve.spawn_foreground", new=fake_spawn_fg),
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
    ):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--foreground-from-supervisor"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    assert read_running(repo) == pre


def test_foreground_from_supervisor_hidden_from_help() -> None:
    result = runner.invoke(app, ["serve", "--help"], catch_exceptions=False)
    assert "--foreground-from-supervisor" not in result.stdout


def test_switch_background_stops_old_starts_new(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18098)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="background",
            config_id="cfg-a",
            port=18098,
            started_at="t",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    (repo / "configs" / "cfg-b.yaml").write_text(
        "id: cfg-b\nruntime: rt-a\nmodel: md-a\n"
        "serve:\n  host: 127.0.0.1\n  port: 18099\n",
        encoding="utf-8",
    )
    killed = {"pid": None, "sig": None}

    def fake_kill(pid, sig):
        killed["pid"] = pid
        killed["sig"] = sig

    with (
        patch("llm_cli.commands.serve.reconcile", lambda _repo: None),
        patch("llm_cli.commands.serve.os.kill", new=fake_kill),
        patch("llm_cli.commands.serve.spawn_background", return_value=5151),
        patch("llm_cli.commands.serve.wait_for_ready", return_value=True),
        patch("llm_cli.commands.serve.port_in_use", return_value=False),
        patch("llm_cli.commands.serve._wait_pid_gone", return_value=True),
    ):
        result = runner.invoke(app, ["switch", "cfg-b"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    assert killed["pid"] == os.getpid()
    rec = read_running(repo)
    assert rec.config_id == "cfg-b"
    assert rec.mode == "background"


def test_switch_errors_when_nothing_running(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["switch", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "nothing running" in result.stdout.lower()


def test_switch_foreground_refuses_with_hint(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="foreground",
            config_id="cfg-a",
            port=1,
            started_at="t",
            pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    with patch("llm_cli.commands.serve.reconcile", lambda _repo: None):
        result = runner.invoke(app, ["switch", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "foreground" in result.stdout.lower()
    assert "ctrl" in result.stdout.lower()


def test_serve_systemd_noop_when_same_config_already_active(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18100)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="systemd",
            config_id="cfg-a",
            port=18100,
            started_at="t",
            unit="llm.service",
        ),
    )
    with (
        patch("llm_cli.commands.serve.systemd_is_active", return_value=True),
        patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True),
        patch("llm_cli.commands.serve.write_if_different", return_value=False) as wid,
        patch("llm_cli.commands.serve.restart_unit") as ru,
    ):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--systemd"], catch_exceptions=False
        )
    assert result.exit_code == 0, result.stdout
    assert "already serving" in result.stdout.lower()
    ru.assert_not_called()
    wid.assert_not_called()
