"""Tests for state/running.json, state/history.jsonl, and reconcile helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_cli.core.lifecycle import (
    LifecycleRecord,
    append_history,
    clear_running,
    history_path,
    is_alive,
    logs_dir,
    read_running,
    reconcile,
    running_path,
    state_dir,
    write_running,
)


def test_state_paths_are_under_repo(tmp_path: Path) -> None:
    repo = tmp_path
    assert state_dir(repo) == repo / "state"
    assert running_path(repo) == repo / "state" / "running.json"
    assert history_path(repo) == repo / "state" / "history.jsonl"
    assert logs_dir(repo) == repo / "state" / "logs"


def test_lifecycle_record_foreground_roundtrip() -> None:
    rec = LifecycleRecord(
        mode="foreground",
        config_id="cfg-a",
        port=8000,
        started_at="2026-05-17T16:00:00Z",
        pid=1234,
        log_path="state/logs/cfg-a.log",
    )
    assert rec.mode == "foreground"
    assert rec.unit is None


def test_lifecycle_record_systemd_roundtrip() -> None:
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=8000,
        started_at="2026-05-17T16:00:00Z",
        unit="llm.service",
    )
    assert rec.pid is None
    assert rec.log_path is None
    assert rec.unit == "llm.service"


def test_read_running_missing_returns_none(tmp_path: Path) -> None:
    assert read_running(tmp_path) is None


def test_write_then_read_running(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=8000,
        started_at="2026-05-17T16:00:00Z",
        pid=1234,
        log_path="state/logs/cfg-a.log",
    )
    write_running(tmp_path, rec)
    got = read_running(tmp_path)
    assert got == rec


def test_write_running_creates_state_dir(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=1,
        started_at="t",
        pid=1,
        log_path="x",
    )
    write_running(tmp_path, rec)
    assert (tmp_path / "state" / "running.json").is_file()


def test_clear_running_is_idempotent(tmp_path: Path) -> None:
    clear_running(tmp_path)  # missing
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=1,
        started_at="t",
        unit="llm.service",
    )
    write_running(tmp_path, rec)
    clear_running(tmp_path)
    assert read_running(tmp_path) is None
    clear_running(tmp_path)  # already gone


def test_read_running_rejects_garbage(tmp_path: Path) -> None:
    path = tmp_path / "state" / "running.json"
    path.parent.mkdir()
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_running(tmp_path)


def test_append_history_creates_file_and_appends(tmp_path: Path) -> None:
    append_history(tmp_path, {"action": "start", "mode": "background"})
    append_history(tmp_path, {"action": "stop", "mode": "background"})
    lines = (
        (tmp_path / "state" / "history.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["action"] == "start"
    assert "ts" in first  # auto-added timestamp


def test_append_history_does_not_overwrite_provided_ts(tmp_path: Path) -> None:
    append_history(tmp_path, {"ts": "fixed", "action": "x"})
    line = (tmp_path / "state" / "history.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(line)["ts"] == "fixed"


def test_is_alive_true_for_self() -> None:
    if os.name == "nt":
        pytest.skip("is_alive is POSIX-oriented; Windows host uses False")
    assert is_alive(os.getpid()) is True


def test_is_alive_false_for_invalid() -> None:
    # PID 0 is special everywhere; never a real process we own.
    assert is_alive(0) is False


def test_is_alive_false_for_dead_pid() -> None:
    # PID 999999 — likely outside the process table; if not, this is still a safe sentinel.
    assert is_alive(999_999) is False


def test_reconcile_keeps_live_pid(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("is_alive is False on Windows; reconcile would reap own PID")
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=1,
        started_at="t",
        pid=os.getpid(),
        log_path="x",
    )
    write_running(tmp_path, rec)
    reconcile(tmp_path)
    assert read_running(tmp_path) == rec


def test_reconcile_drops_dead_pid(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=1,
        started_at="t",
        pid=999_999,
        log_path="x",
    )
    write_running(tmp_path, rec)
    reconcile(tmp_path)
    assert read_running(tmp_path) is None
    hist = (tmp_path / "state" / "history.jsonl").read_text(encoding="utf-8").strip()
    assert "reap-stale" in hist
    assert "cfg-a" in hist


def test_reconcile_drops_systemd_when_inactive(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=1,
        started_at="t",
        unit="llm.service",
    )
    write_running(tmp_path, rec)
    with patch("llm_cli.core.lifecycle._systemd_is_active", return_value=False):
        reconcile(tmp_path)
    assert read_running(tmp_path) is None


def test_reconcile_keeps_systemd_when_active(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=1,
        started_at="t",
        unit="llm.service",
    )
    write_running(tmp_path, rec)
    with patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True):
        reconcile(tmp_path)
    assert read_running(tmp_path) == rec


def test_reconcile_with_no_record_is_noop(tmp_path: Path) -> None:
    reconcile(tmp_path)
    assert read_running(tmp_path) is None
