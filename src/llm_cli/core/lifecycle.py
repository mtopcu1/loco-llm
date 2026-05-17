"""Runtime-lifecycle state: running.json, history.jsonl, PID liveness, reconcile."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LifecycleRecord:
    """In-memory shape of state/running.json. Exactly one record exists at a time."""

    mode: str  # "foreground" | "background" | "systemd"
    config_id: str
    port: int
    started_at: str  # ISO-8601 UTC, e.g. "2026-05-17T16:00:00Z"
    pid: int | None = None
    log_path: str | None = None  # repo-relative POSIX path; None for systemd
    unit: str | None = None  # "llm.service" for systemd; None otherwise


def state_dir(repo: Path) -> Path:
    return repo / "state"


def running_path(repo: Path) -> Path:
    return state_dir(repo) / "running.json"


def history_path(repo: Path) -> Path:
    return state_dir(repo) / "history.jsonl"


def logs_dir(repo: Path) -> Path:
    return state_dir(repo) / "logs"
