"""Runtime-lifecycle state: running.json, history.jsonl, PID liveness, reconcile."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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


def write_running(repo: Path, rec: LifecycleRecord) -> Path:
    """Atomically replace state/running.json with the given record."""
    sd = state_dir(repo)
    sd.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in asdict(rec).items() if v is not None}
    target = running_path(repo)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target


def read_running(repo: Path) -> LifecycleRecord | None:
    path = running_path(repo)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be an object")
    return LifecycleRecord(
        mode=str(raw["mode"]),
        config_id=str(raw["config_id"]),
        port=int(raw["port"]),
        started_at=str(raw["started_at"]),
        pid=int(raw["pid"]) if "pid" in raw else None,
        log_path=str(raw["log_path"]) if "log_path" in raw else None,
        unit=str(raw["unit"]) if "unit" in raw else None,
    )


def clear_running(repo: Path) -> None:
    path = running_path(repo)
    if path.is_file():
        path.unlink()
