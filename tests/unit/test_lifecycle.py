"""Tests for state/running.json, state/history.jsonl, and reconcile helpers."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.lifecycle import (
    LifecycleRecord,
    history_path,
    logs_dir,
    running_path,
    state_dir,
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
