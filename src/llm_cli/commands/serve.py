"""`loco serve` and `loco switch` — start a service in fg/bg/systemd."""
from __future__ import annotations

import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.serve_errors import ServeError
from llm_cli.core.install_record import is_installed
from llm_cli.core.lifecycle import (
    LifecycleRecord,
    append_history,
    clear_running,
    is_alive,
    logs_dir,
    read_running,
    reconcile,
    state_root,
    write_running,
)
from llm_cli.core.repo import scaffold_root
from llm_cli.core.serve_spawn import (
    _bash_single_quote,
    port_in_use,
    spawn_background,
    spawn_foreground,
    wait_for_ready,
)
from llm_cli.core.config_resolve import expand_path_for_serve
from llm_cli.core.model_registry import get_entry as registry_model_entry
from llm_cli.core.params import (
    ParamSpec,
    ParamType,
    derive_env_name,
    validate_params,
)
from llm_cli.core.registry import get_runtime_manifest_merged
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core.systemd_unit import (
    daemon_reload,
    desired_unit_text,
    is_active as systemd_is_active,
    restart_unit,
    stop_unit,
    write_if_different,
)
from llm_cli.core.wsl import to_wsl_path

# Windows' `signal` module has no SIGKILL; POSIX uses 9.
_SIGKILL = int(getattr(signal, "SIGKILL", 9))

if TYPE_CHECKING:
    from llm_cli.core.registry import ConfigRecord

console = Console()


def _fail(message: str, *, hint: str | None = None, code: int = 1) -> NoReturn:
    console.print(f"[red]error:[/red] {message}")
    if hint:
        console.print(hint)
    raise ServeError(message, exit_code=code)


def _tail_log_file(log_path: str | Path, *, max_lines: int = 30) -> list[str]:
    path = Path(log_path)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-max_lines:] if lines else []


def _fail_with_log(message: str, log_path: str | Path, *, code: int = 1) -> NoReturn:
    """Fail after readiness timeout; include recent serve.log lines in the exception."""
    tail = _tail_log_file(log_path, max_lines=40)
    parts = [message, f"serve log: {Path(log_path).resolve()}"]
    if tail:
        parts.append("last log lines:")
        parts.extend(tail[-20:])
    full = "\n".join(parts)
    console.print(f"[red]error:[/red] {message}")
    console.print(f"see {log_path}")
    for line in tail[-12:]:
        console.print(f"  {line}")
    raise ServeError(full, exit_code=code)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_cfg(config_id: str) -> "ConfigRecord":
    cfg = registry.get_config_merged(config_id)
    if cfg is None:
        _fail(f"unknown config {config_id!r}")
    errs = registry.validate_config(scaffold_root(), cfg)
    if errs:
        _fail("; ".join(str(e) for e in errs))
    return cfg


def _serve_script_inner(runtime_path: Path, script_name: str) -> str:
    """Inner bash to cd into runtime asset dir and exec a script."""
    posix = to_wsl_path(runtime_path)
    return (
        "set -euo pipefail; "
        f"cd {_bash_single_quote(posix)}; "
        f"exec bash {_bash_single_quote(script_name)}"
    )


def _serve_env_from_params(
    settings: Settings, cfg_data: dict[str, Any], schema: list[ParamSpec]
) -> dict[str, str]:
    """Build the env dict for serve.sh from validated serve.params."""
    serve = cfg_data["serve"]
    raw_params = serve.get("params") or {}
    coerced, errors = validate_params(schema, raw_params)
    if errors:
        _fail("; ".join(f"{cfg_data.get('id')}: {error}" for error in errors))

    env: dict[str, str] = {
        "LLM_DATA_ROOT": settings.data_root.as_posix(),
        "LLM_REPO_ROOT": scaffold_root().as_posix(),
        "LLM_RUNTIMES": settings.runtimes_dir.as_posix(),
        "LLM_MODELS": settings.models_dir.as_posix(),
        "LLM_CACHE": settings.cache_dir.as_posix(),
        "LLM_CONFIG_ID": str(cfg_data["id"]),
        "LLM_SERVE_HOST": str(serve["host"]),
        "LLM_SERVE_PORT": str(serve["port"]),
    }
    model_raw = cfg_data.get("model")
    if isinstance(model_raw, str):
        ment = registry_model_entry(settings.models_dir, model_raw)
        if ment is not None:
            env["LLM_MODEL_ID"] = model_raw
            env["LLM_MODEL_PATH"] = (
                settings.models_dir / model_raw / ment.artifact.primary
            ).as_posix()
    runtime_id = str(cfg_data["runtime"])
    for spec in schema:
        if spec.key not in coerced:
            continue
        value = coerced[spec.key]
        if spec.type is ParamType.PATH:
            value = expand_path_for_serve(str(value), cfg_data=cfg_data, settings=settings)
        env[derive_env_name(spec, runtime_id=runtime_id)] = str(value)

    merged = os.environ.copy()
    merged.update(env)
    return merged


def _readiness_timeout(cfg_data: dict[str, Any]) -> int:
    ready = cfg_data.get("readiness") or {}
    if isinstance(ready, dict):
        t = ready.get("timeout_seconds")
        if isinstance(t, int) and t > 0:
            return t
    return 600


def _make_healthcheck_probe(
    runtime_path: Path, env: dict[str, str]
):
    """Return a callable: bash healthcheck.sh in runtime dir -> True on exit 0."""
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


def _wait_pid_gone(pid: int, timeout_s: float = 10.0, poll_s: float = 0.2) -> bool:
    """Poll until is_alive(pid) is False or timeout elapses. Returns True if gone."""
    deadline = time.monotonic() + timeout_s
    while is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)
    return True


def _do_background(
    settings: Settings,
    cfg: "ConfigRecord",
    state_base: Path,
    env: dict[str, str],
    runtime_path: Path,
) -> None:
    serve = cfg.data["serve"]
    host = str(serve["host"])
    port = int(serve["port"])
    if port_in_use(host, port):
        _fail(f"port {port} is already in use")

    logs_dir(state_base).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(state_base) / f"{cfg.id}.log").as_posix()
    inner = _serve_script_inner(runtime_path, "serve.sh")
    try:
        pid = spawn_background(inner=inner, log_path=log_path, env=env)
    except RuntimeError as exc:
        _fail_with_log(f"failed to start {cfg.id}: {exc}", log_path)
    timeout = _readiness_timeout(cfg.data)
    probe = _make_healthcheck_probe(runtime_path, env)
    if not wait_for_ready(probe, timeout_s=float(timeout), poll_s=1.0):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        _fail_with_log(f"{cfg.id} did not become ready in {timeout}s", log_path)
    rec = LifecycleRecord(
        mode="background",
        config_id=cfg.id,
        port=port,
        started_at=_utc_now_iso(),
        pid=pid,
        log_path=(Path("state/logs") / f"{cfg.id}.log").as_posix(),
    )
    write_running(state_base, rec)
    append_history(
        state_base, {"action": "start", "mode": "background", "config_id": cfg.id}
    )
    console.print(f"[green]running[/green] {cfg.id} (pid {pid}, port {port})")


def _do_foreground(
    settings: Settings,
    cfg: "ConfigRecord",
    state_base: Path,
    env: dict[str, str],
    runtime_path: Path,
    *,
    from_supervisor: bool,
) -> None:
    serve_obj = cfg.data["serve"]
    host = str(serve_obj["host"])
    port = int(serve_obj["port"])
    if not from_supervisor and port_in_use(host, port):
        _fail(f"port {port} is already in use")

    if from_supervisor:
        inner = _serve_script_inner(runtime_path, "serve.sh")
        _, code = spawn_foreground(
            inner=inner, env=env, on_started=lambda _pid: None
        )
        if code != 0:
            _fail(f"foreground serve exited with code {code}")
        return

    logs_dir(state_base).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(state_base) / f"{cfg.id}.log").as_posix()
    rt_posix = to_wsl_path(runtime_path)
    inner = (
        "set -euo pipefail; "
        f"cd {_bash_single_quote(rt_posix)}; "
        f"exec bash serve.sh "
        f"2>&1 | tee -a {_bash_single_quote(log_path)}"
    )

    def on_started(pid: int) -> None:
        rec = LifecycleRecord(
            mode="foreground",
            config_id=cfg.id,
            port=port,
            started_at=_utc_now_iso(),
            pid=pid,
            log_path=(Path("state/logs") / f"{cfg.id}.log").as_posix(),
        )
        write_running(state_base, rec)
        append_history(
            state_base, {"action": "start", "mode": "foreground", "config_id": cfg.id}
        )

    try:
        _, code = spawn_foreground(inner=inner, env=env, on_started=on_started)
    finally:
        clear_running(state_base)
        append_history(
            state_base, {"action": "stop", "mode": "foreground", "config_id": cfg.id}
        )
    if code != 0:
        _fail(f"foreground serve exited with code {code}")


def _do_systemd(
    settings: Settings,
    cfg: "ConfigRecord",
    state_base: Path,
    env: dict[str, str],
    runtime_path: Path,
) -> None:
    serve_obj = cfg.data["serve"]
    host = str(serve_obj["host"])
    port = int(serve_obj["port"])
    if port_in_use(host, port):
        _fail(f"port {port} is already in use")

    text = desired_unit_text(cfg.id)
    changed = write_if_different(text)
    append_history(
        state_base,
        {
            "action": "systemd-write",
            "unit": "loco.service",
            "config_id": cfg.id,
            "changed": changed,
        },
    )
    if changed:
        daemon_reload()
    restart_unit("loco.service")

    timeout = _readiness_timeout(cfg.data)
    probe = _make_healthcheck_probe(runtime_path, env)

    def combined_probe() -> bool:
        return systemd_is_active("loco.service") and probe()

    if not wait_for_ready(combined_probe, timeout_s=float(timeout), poll_s=1.0):
        try:
            stop_unit("loco.service")
        except RuntimeError:
            pass
        _fail(
            f"{cfg.id} did not become ready in {timeout}s; "
            "see `journalctl --user -u loco.service -n 50`"
        )
    rec = LifecycleRecord(
        mode="systemd",
        config_id=cfg.id,
        port=port,
        started_at=_utc_now_iso(),
        unit="loco.service",
    )
    write_running(state_base, rec)
    append_history(state_base, {"action": "start", "mode": "systemd", "config_id": cfg.id})
    console.print(f"[green]running[/green] {cfg.id} via systemd (port {port})")


def serve_dispatch(
    config_id: str,
    *,
    foreground: bool = False,
    systemd: bool = False,
    foreground_from_supervisor: bool = False,
) -> None:
    """Programmatic serve entry (raises ServeError on failure)."""
    try:
        _serve_dispatch_impl(
            config_id,
            foreground=foreground,
            systemd=systemd,
            foreground_from_supervisor=foreground_from_supervisor,
        )
    except ServeError:
        raise
    except typer.Exit as exc:
        from llm_cli.core.serve_diagnostics import diagnose_serve_failure

        _fail(diagnose_serve_failure(config_id, exit_code=exc.exit_code))


def _serve_dispatch_impl(
    config_id: str,
    *,
    foreground: bool = False,
    systemd: bool = False,
    foreground_from_supervisor: bool = False,
) -> None:
    if foreground and systemd:
        _fail("--foreground and --systemd are mutually exclusive")
    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    cfg = _resolve_cfg(config_id)
    runtime_id = str(cfg.data["runtime"])
    if not is_installed(settings.runtimes_dir, runtime_id):
        _fail(
            f"runtime {runtime_id!r} is not installed",
            hint=f"hint:  loco runtime install {runtime_id}",
        )
    mf = get_runtime_manifest_merged(runtime_id)
    if mf is None:
        _fail(f"unknown runtime {runtime_id!r}")
    runtime_path = mf.path
    cfg_for_env = registry.ConfigRecord(id=cfg.id, path=cfg.path, data=cfg.data)
    env = _serve_env_from_params(settings, cfg_for_env.data, mf.serve_schema)

    existing = read_running(state_base)
    if (
        systemd
        and existing is not None
        and existing.mode == "systemd"
        and existing.config_id == config_id
        and systemd_is_active("loco.service")
    ):
        console.print(f"[green]already serving[/green] {config_id} via systemd")
        return

    if existing and existing.config_id == config_id and not foreground_from_supervisor:
        _fail(
            f"{config_id} already running in {existing.mode}; "
            "use `loco switch` to change config or `loco stop` first"
        )
    if existing and not foreground_from_supervisor:
        _fail(
            f"{existing.config_id} already running in {existing.mode}; "
            "stop it first or use `loco switch`"
        )

    if foreground:
        _do_foreground(
            settings, cfg_for_env, state_base, env, runtime_path, from_supervisor=False
        )
    elif foreground_from_supervisor:
        _do_foreground(
            settings, cfg_for_env, state_base, env, runtime_path, from_supervisor=True
        )
    elif systemd:
        _do_systemd(settings, cfg_for_env, state_base, env, runtime_path)
    else:
        _do_background(settings, cfg_for_env, state_base, env, runtime_path)


def serve(
    config_id: str = typer.Argument(..., help="Config id to start."),
    foreground: bool = typer.Option(
        False, "--foreground", help="Run attached to this terminal."
    ),
    systemd: bool = typer.Option(
        False, "--systemd", help="Bind loco.service to this config."
    ),
    foreground_from_supervisor: bool = typer.Option(
        False, "--foreground-from-supervisor", hidden=True
    ),
) -> None:
    """Start a server for <config_id>."""
    try:
        serve_dispatch(
            config_id,
            foreground=foreground,
            systemd=systemd,
            foreground_from_supervisor=foreground_from_supervisor,
        )
    except ServeError as exc:
        raise typer.Exit(code=exc.exit_code) from exc


def switch(
    config_id: str = typer.Argument(..., help="New config id."),
) -> None:
    """Stop the currently-running service and start <config_id> in the same mode."""
    try:
        _switch_impl(config_id)
    except ServeError as exc:
        raise typer.Exit(code=exc.exit_code) from exc


def _switch_impl(
    config_id: str,
) -> None:
    try:
        _switch_impl_body(config_id)
    except ServeError:
        raise
    except typer.Exit as exc:
        from llm_cli.core.serve_diagnostics import diagnose_serve_failure

        _fail(diagnose_serve_failure(config_id, exit_code=exc.exit_code))


def _switch_impl_body(
    config_id: str,
) -> None:
    settings = resolve(load_settings())
    state_base = state_root(settings)
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        _fail(f"nothing running; use `loco serve {config_id}` instead")
    if rec.mode == "foreground":
        _fail(
            "foreground sessions can't be switched; "
            "Ctrl-C in the original terminal and rerun `loco serve <new>`"
        )

    new_cfg = _resolve_cfg(config_id)
    runtime_id = str(new_cfg.data["runtime"])
    if not is_installed(settings.runtimes_dir, runtime_id):
        _fail(
            f"runtime {runtime_id!r} is not installed",
            hint=f"hint:  loco runtime install {runtime_id}",
        )
    mf = get_runtime_manifest_merged(runtime_id)
    if mf is None:
        _fail(f"unknown runtime {runtime_id!r}")
    runtime_path = mf.path
    new_for_env = registry.ConfigRecord(
        id=new_cfg.id, path=new_cfg.path, data=new_cfg.data
    )
    env = _serve_env_from_params(settings, new_for_env.data, mf.serve_schema)
    old_id = rec.config_id

    if rec.mode == "background":
        if rec.pid is None:
            _fail("running record has no pid; aborting switch")
        try:
            os.kill(rec.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_pid_gone(rec.pid, timeout_s=10.0):
            try:
                os.kill(rec.pid, _SIGKILL)
            except ProcessLookupError:
                pass
        clear_running(state_base)
        append_history(
            state_base,
            {
                "action": "switch",
                "mode": "background",
                "from": old_id,
                "to": config_id,
            },
        )
        _do_background(settings, new_for_env, state_base, env, runtime_path)
        return

    if rec.mode == "systemd":
        clear_running(state_base)
        append_history(
            state_base,
            {
                "action": "switch",
                "mode": "systemd",
                "from": old_id,
                "to": config_id,
            },
        )
        _do_systemd(settings, new_for_env, state_base, env, runtime_path)
        return

    _fail(f"unknown mode {rec.mode!r}")
