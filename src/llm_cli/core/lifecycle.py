"""Runtime-lifecycle state: running.json, history.jsonl, PID liveness, reconcile."""
from __future__ import annotations

import asyncio
import json
import os as _os
import subprocess as _subprocess
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_cli.core.settings import Settings


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


def state_root(settings: "Settings") -> Path:
    """Base directory for state/ (dev checkout or data_root for bundle installs)."""
    if settings.repo_root is not None:
        return settings.repo_root
    return settings.data_root


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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_history(repo: Path, event: dict[str, Any]) -> None:
    """Append a JSON object as one line to state/history.jsonl."""
    sd = state_dir(repo)
    sd.mkdir(parents=True, exist_ok=True)
    line = dict(event)
    line.setdefault("ts", _utc_now_iso())
    with history_path(repo).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    if line.get("action") in ("start", "stop", "switch"):
        emit_lifecycle_event(repo, line)


_LifecycleHandler = Callable[[dict[str, Any]], Awaitable[None]]


class _LifecycleEventBus:
    def __init__(self) -> None:
        self._handlers: list[_LifecycleHandler] = []

    def subscribe_async(self, handler: _LifecycleHandler) -> None:
        self._handlers.append(handler)

    def publish(self, event: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for handler in self._handlers:
            loop.create_task(handler(event))


_LIFECYCLE_BUS: _LifecycleEventBus | None = None


def event_bus() -> _LifecycleEventBus:
    global _LIFECYCLE_BUS
    if _LIFECYCLE_BUS is None:
        _LIFECYCLE_BUS = _LifecycleEventBus()
    return _LIFECYCLE_BUS


def emit_lifecycle_event(repo: Path, event: dict[str, Any]) -> None:
    """Publish start/stop/switch events for dashboard subscribers."""
    action = event.get("action")
    enriched: dict[str, Any] | None = None
    if action == "start":
        if "config_id" not in event:
            return
        rec = read_running(repo)
        cfg_id = str(event["config_id"])
        runtime_id: str | None = None
        from llm_cli.core import registry

        cfg = registry.get_config_merged(cfg_id)
        if cfg and isinstance(cfg.data.get("runtime"), str):
            runtime_id = cfg.data["runtime"]
        enriched = {
            "action": "start",
            "config_id": cfg_id,
            "runtime_id": runtime_id,
            "port": rec.port if rec else event.get("port"),
        }
    elif action == "stop":
        if "config_id" not in event:
            return
        enriched = {"action": "stop", "config_id": str(event["config_id"])}
    elif action == "switch":
        enriched = {
            "action": "switch",
            "from": event.get("from"),
            "to": event.get("to"),
        }
    if enriched is not None:
        event_bus().publish(enriched)


def read_history(repo: Path) -> list[dict[str, Any]]:
    path = history_path(repo)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def is_alive(pid: int) -> bool:
    """Return True if pid identifies a live process owned by this user.

    POSIX: `kill(pid, 0)` raises ESRCH if dead, EPERM if alive-but-not-ours,
    or succeeds if alive-and-ours. We treat EPERM as alive (the process exists).

    Windows: best-effort; lifecycle commands run in WSL, so a False return on
    Windows is fine for unit tests on the host.
    """
    if pid <= 0:
        return False
    if _os.name == "nt":
        return False
    try:
        _os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _systemd_is_active(unit: str) -> bool:
    """True if `systemctl --user is-active <unit>` prints 'active'."""
    try:
        r = _subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        return False
    return r.stdout.strip() == "active"


def reconcile(repo: Path) -> None:
    """Drop a stale record from running.json. Side-effect: history append on drop."""
    rec = read_running(repo)
    if rec is None:
        return
    if rec.mode in ("foreground", "background"):
        if rec.pid is None or not is_alive(rec.pid):
            append_history(
                repo,
                {
                    "action": "reap-stale",
                    "mode": rec.mode,
                    "config_id": rec.config_id,
                    "reason": "pid-gone",
                },
            )
            clear_running(repo)
        return
    if rec.mode == "systemd":
        if not rec.unit or not _systemd_is_active(rec.unit):
            append_history(
                repo,
                {
                    "action": "reap-stale",
                    "mode": "systemd",
                    "config_id": rec.config_id,
                    "reason": "unit-inactive",
                },
            )
            clear_running(repo)
        return


class LifecycleError(Exception):
    """Raised when a lifecycle operation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def stop_instance() -> None:
    """Stop whatever is running (idempotent). Raises LifecycleError on failure."""
    import signal
    import time

    from llm_cli.core.settings import load_settings, resolve
    from llm_cli.core.systemd_unit import stop_unit

    _SIGKILL = int(getattr(signal, "SIGKILL", 9))

    def _wait_pid_gone(pid: int, timeout_s: float = 10.0, poll_s: float = 0.2) -> bool:
        deadline = time.monotonic() + timeout_s
        while is_alive(pid):
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_s)
        return True

    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        return
    if rec.mode in ("foreground", "background"):
        if rec.pid is None:
            clear_running(state_base)
            return
        try:
            _os.kill(rec.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_pid_gone(rec.pid, timeout_s=10.0):
            try:
                _os.kill(rec.pid, _SIGKILL)
            except ProcessLookupError:
                pass
            _wait_pid_gone(rec.pid, timeout_s=2.0)
        clear_running(state_base)
        append_history(
            state_base, {"action": "stop", "mode": rec.mode, "config_id": rec.config_id}
        )
        return
    if rec.mode == "systemd":
        try:
            stop_unit("llm.service")
        except RuntimeError as exc:
            raise LifecycleError(f"systemctl stop failed: {exc}") from exc
        clear_running(state_base)
        append_history(
            state_base, {"action": "stop", "mode": "systemd", "config_id": rec.config_id}
        )
        return
    raise LifecycleError(f"unknown mode {rec.mode!r}")


def serve_instance(config_id: str, *, mode: str) -> None:
    """Start a config in background or systemd mode."""
    import typer

    from llm_cli.commands.serve import serve_dispatch

    if mode not in ("background", "systemd"):
        raise LifecycleError(f"unsupported mode {mode!r}")
    try:
        serve_dispatch(
            config_id,
            foreground=False,
            systemd=(mode == "systemd"),
        )
    except typer.Exit as exc:
        raise LifecycleError(f"serve exited with code {exc.exit_code}") from exc


def switch_instance(config_id: str) -> None:
    """Switch the running service to another config."""
    import typer

    from llm_cli.commands.serve import switch as switch_cmd

    try:
        switch_cmd(config_id)
    except typer.Exit as exc:
        raise LifecycleError(f"switch exited with code {exc.exit_code}") from exc
