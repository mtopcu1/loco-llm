"""Serve mode strategies: background, foreground, and systemd."""
from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, NoReturn

from llm_cli.core.lifecycle import (
    LifecycleRecord,
    append_history,
    clear_running,
    logs_dir,
    write_running,
)
from llm_cli.core.serve_errors import ServeError
from llm_cli.core.serve_spawn import _bash_single_quote
from llm_cli.core.settings import Settings
from llm_cli.core.time import utc_now_iso
from llm_cli.core.wsl import to_wsl_path

if TYPE_CHECKING:
    from llm_cli.core.registry import ConfigRecord

ServeMessageFn = Callable[[str], None] | None


@dataclass(frozen=True)
class ServeStartContext:
    """Shared inputs for starting a config in any serve mode."""

    settings: Settings
    cfg: "ConfigRecord"
    state_base: Path
    env: dict[str, str]
    runtime_path: Path
    on_message: ServeMessageFn = None
    from_supervisor: bool = False


def _fail(message: str, *, hint: str | None = None, code: int = 1) -> NoReturn:
    raise ServeError(message, exit_code=code, hint=hint)


def _tail_log_file(log_path: str | Path, *, max_lines: int = 30) -> list[str]:
    path = Path(log_path)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-max_lines:] if lines else []


def _fail_with_log(message: str, log_path: str | Path, *, code: int = 1) -> NoReturn:
    tail = _tail_log_file(log_path, max_lines=40)
    parts = [message, f"serve log: {Path(log_path).resolve()}"]
    if tail:
        parts.append("last log lines:")
        parts.extend(tail[-20:])
    raise ServeError("\n".join(parts), exit_code=code)


def _host_port(cfg: "ConfigRecord") -> tuple[str, int]:
    serve = cfg.data["serve"]
    return str(serve["host"]), int(serve["port"])


def _serve():
    """Import serve late so integration tests can patch ``llm_cli.core.serve``."""
    from llm_cli.core import serve as serve_mod

    return serve_mod


def _ensure_port_available(host: str, port: int) -> None:
    if _serve().port_in_use(host, port):
        _fail(f"port {port} is already in use")


def _readiness_timeout(cfg_data: dict[str, Any]) -> int:
    ready = cfg_data.get("readiness") or {}
    if isinstance(ready, dict):
        t = ready.get("timeout_seconds")
        if isinstance(t, int) and t > 0:
            return t
    return 600


def _serve_script_inner(runtime_path: Path, script_name: str) -> str:
    posix = to_wsl_path(runtime_path)
    return (
        "set -euo pipefail; "
        f"cd {_bash_single_quote(posix)}; "
        f"exec bash {_bash_single_quote(script_name)}"
    )


def _make_healthcheck_probe(runtime_path: Path, env: dict[str, str]):
    import subprocess

    inner = _serve_script_inner(runtime_path, "healthcheck.sh")

    def probe() -> bool:
        r = subprocess.run(
            ["bash", "-lc", inner],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode == 0

    return probe


def _wait_until_ready(
    ctx: ServeStartContext,
    *,
    log_path: str | Path | None = None,
    extra_probe: Callable[[], bool] | None = None,
) -> None:
    timeout = _readiness_timeout(ctx.cfg.data)
    base_probe = _make_healthcheck_probe(ctx.runtime_path, ctx.env)

    def probe() -> bool:
        ok = base_probe()
        if extra_probe is not None:
            ok = ok and extra_probe()
        return ok

    if _serve().wait_for_ready(probe, timeout_s=float(timeout), poll_s=1.0):
        return
    if log_path is not None:
        _fail_with_log(
            f"{ctx.cfg.id} did not become ready in {timeout}s",
            log_path,
        )
    _fail(
        f"{ctx.cfg.id} did not become ready in {timeout}s; "
        "see `journalctl --user -u loco.service -n 50`"
    )


def start_background(ctx: ServeStartContext) -> None:
    host, port = _host_port(ctx.cfg)
    _ensure_port_available(host, port)

    ctx.state_base.mkdir(parents=True, exist_ok=True)
    logs_dir(ctx.state_base).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(ctx.state_base) / f"{ctx.cfg.id}.log").as_posix()
    inner = _serve_script_inner(ctx.runtime_path, "serve.sh")
    try:
        pid = _serve().spawn_background(inner=inner, log_path=log_path, env=ctx.env)
    except RuntimeError as exc:
        _fail_with_log(f"failed to start {ctx.cfg.id}: {exc}", log_path)

    try:
        _wait_until_ready(ctx, log_path=log_path)
    except ServeError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        raise

    rec = LifecycleRecord(
        mode="background",
        config_id=ctx.cfg.id,
        port=port,
        started_at=utc_now_iso(),
        pid=pid,
        log_path=(Path("state/logs") / f"{ctx.cfg.id}.log").as_posix(),
    )
    write_running(ctx.state_base, rec)
    append_history(
        ctx.state_base,
        {"action": "start", "mode": "background", "config_id": ctx.cfg.id},
    )
    if ctx.on_message is not None:
        ctx.on_message(f"running {ctx.cfg.id} (pid {pid}, port {port})")


def start_foreground(ctx: ServeStartContext) -> None:
    host, port = _host_port(ctx.cfg)
    if not ctx.from_supervisor:
        _ensure_port_available(host, port)

    if ctx.from_supervisor:
        inner = _serve_script_inner(ctx.runtime_path, "serve.sh")
        _, code = _serve().spawn_foreground(
            inner=inner, env=ctx.env, on_started=lambda _pid: None
        )
        if code != 0:
            _fail(f"foreground serve exited with code {code}")
        return

    logs_dir(ctx.state_base).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(ctx.state_base) / f"{ctx.cfg.id}.log").as_posix()
    rt_posix = to_wsl_path(ctx.runtime_path)
    inner = (
        "set -euo pipefail; "
        f"cd {_bash_single_quote(rt_posix)}; "
        f"exec bash serve.sh "
        f"2>&1 | tee -a {_bash_single_quote(log_path)}"
    )

    def on_started(pid: int) -> None:
        rec = LifecycleRecord(
            mode="foreground",
            config_id=ctx.cfg.id,
            port=port,
            started_at=utc_now_iso(),
            pid=pid,
            log_path=(Path("state/logs") / f"{ctx.cfg.id}.log").as_posix(),
        )
        write_running(ctx.state_base, rec)
        append_history(
            ctx.state_base,
            {"action": "start", "mode": "foreground", "config_id": ctx.cfg.id},
        )

    try:
        _, code = _serve().spawn_foreground(inner=inner, env=ctx.env, on_started=on_started)
    finally:
        clear_running(ctx.state_base)
        append_history(
            ctx.state_base,
            {"action": "stop", "mode": "foreground", "config_id": ctx.cfg.id},
        )
    if code != 0:
        _fail(f"foreground serve exited with code {code}")


def start_systemd(ctx: ServeStartContext) -> None:
    host, port = _host_port(ctx.cfg)
    _ensure_port_available(host, port)

    s = _serve()
    text = s.desired_unit_text(ctx.cfg.id)
    changed = s.write_if_different(text)
    append_history(
        ctx.state_base,
        {
            "action": "systemd-write",
            "unit": "loco.service",
            "config_id": ctx.cfg.id,
            "changed": changed,
        },
    )
    if changed:
        s.daemon_reload()
    s.restart_unit("loco.service")

    try:
        _wait_until_ready(
            ctx,
            extra_probe=lambda: s.systemd_is_active("loco.service"),
        )
    except ServeError:
        try:
            s.stop_unit("loco.service")
        except RuntimeError:
            pass
        raise

    rec = LifecycleRecord(
        mode="systemd",
        config_id=ctx.cfg.id,
        port=port,
        started_at=utc_now_iso(),
        unit="loco.service",
    )
    write_running(ctx.state_base, rec)
    append_history(
        ctx.state_base,
        {"action": "start", "mode": "systemd", "config_id": ctx.cfg.id},
    )
    if ctx.on_message is not None:
        ctx.on_message(f"running {ctx.cfg.id} via systemd (port {port})")


MODE_STARTERS: dict[str, Callable[[ServeStartContext], None]] = {
    "background": start_background,
    "foreground": start_foreground,
    "systemd": start_systemd,
}
