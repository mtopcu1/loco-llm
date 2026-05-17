"""Tests for state/running.json, state/history.jsonl, and reconcile helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.lifecycle import (
    LifecycleRecord,
    clear_running,
    history_path,
    logs_dir,
    read_running,
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
