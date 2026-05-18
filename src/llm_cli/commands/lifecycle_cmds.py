"""`llm stop`, `llm status`, `llm logs`."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone

import typer
from rich.console import Console

from llm_cli.core.lifecycle import (
    append_history,
    clear_running,
    is_alive,
    read_running,
    reconcile,
    state_root,
)
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.systemd_unit import is_active as systemd_is_active
from llm_cli.core.systemd_unit import stop_unit

console = Console()

# Windows' `signal` module has no SIGKILL; POSIX uses 9.
_SIGKILL = int(getattr(signal, "SIGKILL", 9))


def _wait_pid_gone(pid: int, timeout_s: float = 10.0, poll_s: float = 0.2) -> bool:
    deadline = time.monotonic() + timeout_s
    while is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)
    return True


def stop() -> None:
    """Stop whatever is running (idempotent)."""
    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        console.print("nothing running")
        return
    if rec.mode in ("foreground", "background"):
        if rec.pid is None:
            clear_running(state_base)
            console.print("cleared stale record (no pid)")
            return
        try:
            os.kill(rec.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_pid_gone(rec.pid, timeout_s=10.0):
            try:
                os.kill(rec.pid, _SIGKILL)
            except ProcessLookupError:
                pass
            _wait_pid_gone(rec.pid, timeout_s=2.0)
        clear_running(state_base)
        append_history(
            state_base, {"action": "stop", "mode": rec.mode, "config_id": rec.config_id}
        )
        console.print(f"[green]stopped[/green] {rec.config_id}")
        return
    if rec.mode == "systemd":
        try:
            stop_unit("llm.service")
        except RuntimeError as exc:
            console.print(f"[yellow]warning:[/yellow] systemctl stop failed: {exc}")
        clear_running(state_base)
        append_history(
            state_base, {"action": "stop", "mode": "systemd", "config_id": rec.config_id}
        )
        console.print(f"[green]stopped[/green] {rec.config_id} (systemd)")
        return
    console.print(f"[red]error:[/red] unknown mode {rec.mode!r}")
    raise typer.Exit(code=1)


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _format_uptime(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def status(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
) -> None:
    """Print what's running. Always exits 0."""
    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        if as_json:
            typer.echo(json.dumps({"running": False}))
            return
        console.print("status: not running")
        return

    started = _parse_iso(rec.started_at)
    uptime_s = (
        int((datetime.now(timezone.utc) - started).total_seconds()) if started else 0
    )
    pid_alive = is_alive(rec.pid) if rec.pid is not None else None

    if as_json:
        payload: dict[str, object] = {
            "running": True,
            "mode": rec.mode,
            "config_id": rec.config_id,
            "port": rec.port,
            "started_at": rec.started_at,
            "uptime_seconds": uptime_s,
        }
        if rec.pid is not None:
            payload["pid"] = rec.pid
            payload["pid_alive"] = bool(pid_alive)
        if rec.log_path is not None:
            payload["log_path"] = rec.log_path
        if rec.unit is not None:
            payload["unit"] = rec.unit
            payload["systemd_active"] = systemd_is_active(rec.unit)
        typer.echo(json.dumps(payload, indent=2))
        return

    console.print("status: running")
    console.print(f"mode:   {rec.mode}")
    console.print(f"config: {rec.config_id}")
    console.print(f"port:   {rec.port}")
    if rec.mode == "systemd":
        console.print(f"unit:   {rec.unit}")
        u = rec.unit or "llm.service"
        console.print(f"journalctl: journalctl --user -u {u}")
    else:
        console.print(f"pid:    {rec.pid}")
        console.print(f"log:    {rec.log_path}")
    console.print(f"uptime: {_format_uptime(uptime_s)}")


def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow appends."),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of trailing lines."),
) -> None:
    """Tail the log of the currently-running service."""
    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        console.print("nothing running")
        raise typer.Exit(code=1)
    if rec.mode == "systemd":
        cmd = ["journalctl", "--user", "-u", rec.unit or "llm.service", "-n", str(lines)]
        if follow:
            cmd.append("-f")
        raise typer.Exit(code=subprocess.call(cmd))
    if rec.log_path is None:
        console.print("[red]error:[/red] running record has no log_path")
        raise typer.Exit(code=1)
    log_file = (state_base / rec.log_path).resolve()
    if not log_file.is_file():
        console.print(f"[yellow]warning:[/yellow] log file missing: {log_file}")
        raise typer.Exit(code=0)
    cmd: list[str] = ["tail", "-n", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(str(log_file))
    raise typer.Exit(code=subprocess.call(cmd))
