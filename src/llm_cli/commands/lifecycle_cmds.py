"""`loco stop`, `loco status`, `loco logs`."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import typer
from rich.console import Console

from llm_cli.core.lifecycle import (
    LifecycleError,
    is_alive,
    read_running,
    reconcile,
    state_root,
    stop_instance,
)
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.systemd_unit import is_active as systemd_is_active

console = Console()


def stop() -> None:
    """Stop whatever is running (idempotent)."""
    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        console.print("nothing running")
        return
    try:
        stopped = stop_instance(strict_systemd=False)
    except LifecycleError as exc:
        console.print(f"[red]error:[/red] {exc.message}")
        raise typer.Exit(code=1) from exc
    if stopped is None:
        console.print("nothing running")
        return
    if rec.mode == "systemd":
        console.print(f"[green]stopped[/green] {stopped} (systemd)")
    else:
        console.print(f"[green]stopped[/green] {stopped}")


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
        u = rec.unit or "loco.service"
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
        cmd = ["journalctl", "--user", "-u", rec.unit or "loco.service", "-n", str(lines)]
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
    if follow:
        cmd = ["tail", "-f", str(log_file)]
        raise typer.Exit(code=subprocess.call(cmd))
    text = log_file.read_text(encoding="utf-8", errors="replace")
    tail_lines = text.splitlines()[-lines:] if lines > 0 else []
    for line in tail_lines:
        typer.echo(line)
