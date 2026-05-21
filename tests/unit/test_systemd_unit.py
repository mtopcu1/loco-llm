"""Tests for systemd_unit: template, write-if-different, and systemctl wrappers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llm_cli.core.systemd_unit import (
    daemon_reload,
    desired_unit_text,
    is_active,
    restart_unit,
    stop_unit,
    unit_path,
    write_if_different,
)


def test_desired_unit_text_contains_config_and_exec() -> None:
    txt = desired_unit_text("vllm-cuda__qwen2-7b-instruct__default")
    assert "AUTO-GENERATED" in txt
    assert (
        "Description=LocalLLM service (config: vllm-cuda__qwen2-7b-instruct__default)"
        in txt
    )
    assert "ExecStart=" in txt
    assert "vllm-cuda__qwen2-7b-instruct__default --foreground-from-supervisor" in txt
    assert "Restart=on-failure" in txt
    assert "WantedBy=default.target" in txt


def test_desired_unit_text_is_deterministic() -> None:
    assert desired_unit_text("a") == desired_unit_text("a")
    assert desired_unit_text("a") != desired_unit_text("b")


def test_unit_path_uses_xdg_config_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert unit_path() == tmp_path / "systemd" / "user" / "loco.service"


def test_unit_path_falls_back_to_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert unit_path() == tmp_path / ".config" / "systemd" / "user" / "loco.service"


def test_write_if_different_creates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    changed = write_if_different("hello\n")
    assert changed is True
    assert unit_path().read_text(encoding="utf-8") == "hello\n"


def test_write_if_different_no_op_on_same_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_if_different("v1\n")
    changed = write_if_different("v1\n")
    assert changed is False


def test_write_if_different_replaces_on_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_if_different("v1\n")
    changed = write_if_different("v2\n")
    assert changed is True
    assert unit_path().read_text(encoding="utf-8") == "v2\n"


def test_daemon_reload_calls_systemctl_user() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    daemon_reload(runner=runner)
    runner.assert_called_once()
    cmd = runner.call_args[0][0]
    assert cmd == ["systemctl", "--user", "daemon-reload"]


def test_restart_unit_calls_systemctl_restart() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    restart_unit("loco.service", runner=runner)
    cmd = runner.call_args[0][0]
    assert cmd == ["systemctl", "--user", "restart", "loco.service"]


def test_stop_unit_calls_systemctl_stop() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    stop_unit("loco.service", runner=runner)
    cmd = runner.call_args[0][0]
    assert cmd == ["systemctl", "--user", "stop", "loco.service"]


def test_is_active_true_when_stdout_active() -> None:
    runner = MagicMock(
        return_value=MagicMock(returncode=0, stdout="active\n", stderr="")
    )
    assert is_active("loco.service", runner=runner) is True


def test_is_active_false_when_stdout_inactive() -> None:
    runner = MagicMock(
        return_value=MagicMock(returncode=3, stdout="inactive\n", stderr="")
    )
    assert is_active("loco.service", runner=runner) is False


def test_is_active_false_when_systemctl_missing() -> None:
    def runner(cmd, **kw):
        raise FileNotFoundError("systemctl")

    assert is_active("loco.service", runner=runner) is False


def test_restart_unit_raises_on_nonzero() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=2, stdout="", stderr="boom"))
    with pytest.raises(RuntimeError):
        restart_unit("loco.service", runner=runner)
