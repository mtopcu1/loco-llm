"""`llm serve` and `llm switch` — start a service in fg/bg/systemd."""
from __future__ import annotations

import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.install_record import is_installed
from llm_cli.core.lifecycle import (
    LifecycleRecord,
    append_history,
    clear_running,
    is_alive,
    logs_dir,
    read_running,
    reconcile,
    write_running,
)
from llm_cli.core.repo import repo_root
from llm_cli.core.serve_spawn import (
    _bash_single_quote,
    build_serve_inner,
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
from llm_cli.core.registry import get_runtime_manifest
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_cfg(repo: Path, config_id: str) -> "ConfigRecord":
    cfg = registry.get_config(repo, config_id)
    if cfg is None:
        console.print(f"[red]error:[/red] unknown config {config_id!r}")
        raise typer.Exit(code=1)
    errs = registry.validate_config(repo, cfg)
    if errs:
        for e in errs:
            console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)
    return cfg


def _serve_env_from_params(
    settings: Settings, cfg_data: dict[str, Any], schema: list[ParamSpec]
) -> dict[str, str]:
    """Build the env dict for serve.sh from validated serve.params."""
    serve = cfg_data["serve"]
    raw_params = serve.get("params") or {}
    coerced, errors = validate_params(schema, raw_params)
    if errors:
        for error in errors:
            console.print(f"[red]error:[/red] {cfg_data.get('id')}: {error}")
        raise typer.Exit(code=1)

    env: dict[str, str] = {
        "LLM_DATA_ROOT": settings.data_root.as_posix(),
        "LLM_REPO_ROOT": settings.repo_root.as_posix(),
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
    settings: Settings, runtime_id: str, env: dict[str, str]
):
    """Return a callable: bash runtimes/<rt>/healthcheck.sh -> True on exit 0."""
    import subprocess

    repo_posix = to_wsl_path(settings.repo_root)
    inner = build_serve_inner(
        repo_posix=repo_posix,
        script_posix_relpath=f"runtimes/{runtime_id}/healthcheck.sh",
    )

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
    settings: Settings, cfg: "ConfigRecord", repo: Path, env: dict[str, str]
) -> None:
    serve = cfg.data["serve"]
    host = str(serve["host"])
    port = int(serve["port"])
    if port_in_use(host, port):
        console.print(f"[red]error:[/red] port {port} is already in use")
        raise typer.Exit(code=1)

    logs_dir(repo).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(repo) / f"{cfg.id}.log").as_posix()
    repo_posix = to_wsl_path(settings.repo_root)
    inner = build_serve_inner(
        repo_posix=repo_posix,
        script_posix_relpath=f"runtimes/{cfg.data['runtime']}/serve.sh",
    )
    pid = spawn_background(inner=inner, log_path=log_path, env=env)
    timeout = _readiness_timeout(cfg.data)
    probe = _make_healthcheck_probe(settings, str(cfg.data["runtime"]), env)
    if not wait_for_ready(probe, timeout_s=float(timeout), poll_s=1.0):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        console.print(
            f"[red]error:[/red] {cfg.id} did not become ready in {timeout}s; "
            f"see {log_path}"
        )
        raise typer.Exit(code=1)
    rec = LifecycleRecord(
        mode="background",
        config_id=cfg.id,
        port=port,
        started_at=_utc_now_iso(),
        pid=pid,
        log_path=(Path("state/logs") / f"{cfg.id}.log").as_posix(),
    )
    write_running(repo, rec)
    append_history(
        repo, {"action": "start", "mode": "background", "config_id": cfg.id}
    )
    console.print(f"[green]running[/green] {cfg.id} (pid {pid}, port {port})")


def _do_foreground(
    settings: Settings,
    cfg: "ConfigRecord",
    repo: Path,
    env: dict[str, str],
    *,
    from_supervisor: bool,
) -> None:
    serve_obj = cfg.data["serve"]
    host = str(serve_obj["host"])
    port = int(serve_obj["port"])
    if not from_supervisor and port_in_use(host, port):
        console.print(f"[red]error:[/red] port {port} is already in use")
        raise typer.Exit(code=1)

    repo_posix = to_wsl_path(settings.repo_root)
    if from_supervisor:
        inner = build_serve_inner(
            repo_posix=repo_posix,
            script_posix_relpath=f"runtimes/{cfg.data['runtime']}/serve.sh",
        )
        _, code = spawn_foreground(
            inner=inner, env=env, on_started=lambda _pid: None
        )
        raise typer.Exit(code=code)

    logs_dir(repo).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(repo) / f"{cfg.id}.log").as_posix()
    rt = str(cfg.data["runtime"])
    inner = (
        "set -euo pipefail; "
        f"cd {_bash_single_quote(repo_posix)}; "
        f"exec bash {_bash_single_quote(f'runtimes/{rt}/serve.sh')} "
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
        write_running(repo, rec)
        append_history(
            repo, {"action": "start", "mode": "foreground", "config_id": cfg.id}
        )

    try:
        _, code = spawn_foreground(inner=inner, env=env, on_started=on_started)
    finally:
        clear_running(repo)
        append_history(
            repo, {"action": "stop", "mode": "foreground", "config_id": cfg.id}
        )
    raise typer.Exit(code=code)


def _do_systemd(
    settings: Settings, cfg: "ConfigRecord", repo: Path, env: dict[str, str]
) -> None:
    serve_obj = cfg.data["serve"]
    host = str(serve_obj["host"])
    port = int(serve_obj["port"])
    if port_in_use(host, port):
        console.print(f"[red]error:[/red] port {port} is already in use")
        raise typer.Exit(code=1)

    text = desired_unit_text(cfg.id)
    changed = write_if_different(text)
    append_history(
        repo,
        {
            "action": "systemd-write",
            "unit": "llm.service",
            "config_id": cfg.id,
            "changed": changed,
        },
    )
    if changed:
        daemon_reload()
    restart_unit("llm.service")

    timeout = _readiness_timeout(cfg.data)
    probe = _make_healthcheck_probe(settings, str(cfg.data["runtime"]), env)

    def combined_probe() -> bool:
        return systemd_is_active("llm.service") and probe()

    if not wait_for_ready(combined_probe, timeout_s=float(timeout), poll_s=1.0):
        try:
            stop_unit("llm.service")
        except RuntimeError:
            pass
        console.print(
            f"[red]error:[/red] {cfg.id} did not become ready in {timeout}s; "
            f"see `journalctl --user -u llm.service -n 50`"
        )
        raise typer.Exit(code=1)
    rec = LifecycleRecord(
        mode="systemd",
        config_id=cfg.id,
        port=port,
        started_at=_utc_now_iso(),
        unit="llm.service",
    )
    write_running(repo, rec)
    append_history(repo, {"action": "start", "mode": "systemd", "config_id": cfg.id})
    console.print(f"[green]running[/green] {cfg.id} via systemd (port {port})")


def serve_dispatch(
    config_id: str,
    *,
    foreground: bool = False,
    systemd: bool = False,
    foreground_from_supervisor: bool = False,
) -> None:
    """Programmatic serve entry (raises typer.Exit)."""
    if foreground and systemd:
        console.print(
            "[red]error:[/red] --foreground and --systemd are mutually exclusive"
        )
        raise typer.Exit(code=1)
    repo = repo_root()
    reconcile(repo)
    cfg = _resolve_cfg(repo, config_id)
    settings = resolve(load_settings())
    runtime_id = str(cfg.data["runtime"])
    if not is_installed(settings.runtimes_dir, runtime_id):
        console.print(f"[red]error:[/red] runtime {runtime_id!r} is not installed")
        console.print(f"hint:  llm runtime install {runtime_id}")
        raise typer.Exit(code=1)
    mf = get_runtime_manifest(repo, runtime_id)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    cfg_for_env = registry.ConfigRecord(id=cfg.id, path=cfg.path, data=cfg.data)
    env = _serve_env_from_params(settings, cfg_for_env.data, mf.serve_schema)

    existing = read_running(repo)
    if (
        systemd
        and existing is not None
        and existing.mode == "systemd"
        and existing.config_id == config_id
        and systemd_is_active("llm.service")
    ):
        console.print(f"[green]already serving[/green] {config_id} via systemd")
        return

    if existing and existing.config_id == config_id and not foreground_from_supervisor:
        console.print(
            f"[red]error:[/red] {config_id} already running in {existing.mode}; "
            f"use `llm switch` to change config or `llm stop` first"
        )
        raise typer.Exit(code=1)
    if existing and not foreground_from_supervisor:
        console.print(
            f"[red]error:[/red] {existing.config_id} already running in {existing.mode}; "
            "stop it first or use `llm switch`"
        )
        raise typer.Exit(code=1)

    if foreground:
        _do_foreground(settings, cfg_for_env, repo, env, from_supervisor=False)
    elif foreground_from_supervisor:
        _do_foreground(settings, cfg_for_env, repo, env, from_supervisor=True)
    elif systemd:
        _do_systemd(settings, cfg_for_env, repo, env)
    else:
        _do_background(settings, cfg_for_env, repo, env)


def serve(
    config_id: str = typer.Argument(..., help="Config id to start."),
    foreground: bool = typer.Option(
        False, "--foreground", help="Run attached to this terminal."
    ),
    systemd: bool = typer.Option(
        False, "--systemd", help="Bind llm.service to this config."
    ),
    foreground_from_supervisor: bool = typer.Option(
        False, "--foreground-from-supervisor", hidden=True
    ),
) -> None:
    """Start a server for <config_id>."""
    serve_dispatch(
        config_id,
        foreground=foreground,
        systemd=systemd,
        foreground_from_supervisor=foreground_from_supervisor,
    )


def switch(
    config_id: str = typer.Argument(..., help="New config id."),
) -> None:
    """Stop the currently-running service and start <config_id> in the same mode."""
    repo = repo_root()
    reconcile(repo)
    rec = read_running(repo)
    if rec is None:
        console.print(
            f"[red]error:[/red] nothing running; use `llm serve {config_id}` instead"
        )
        raise typer.Exit(code=1)
    if rec.mode == "foreground":
        console.print(
            "[red]error:[/red] foreground sessions can't be switched; "
            "Ctrl-C in the original terminal and rerun `llm serve <new>`"
        )
        raise typer.Exit(code=1)

    settings = resolve(load_settings())
    new_cfg = _resolve_cfg(repo, config_id)
    runtime_id = str(new_cfg.data["runtime"])
    if not is_installed(settings.runtimes_dir, runtime_id):
        console.print(f"[red]error:[/red] runtime {runtime_id!r} is not installed")
        console.print(f"hint:  llm runtime install {runtime_id}")
        raise typer.Exit(code=1)
    mf = get_runtime_manifest(repo, runtime_id)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    new_for_env = registry.ConfigRecord(
        id=new_cfg.id, path=new_cfg.path, data=new_cfg.data
    )
    env = _serve_env_from_params(settings, new_for_env.data, mf.serve_schema)
    old_id = rec.config_id

    if rec.mode == "background":
        if rec.pid is None:
            console.print("[red]error:[/red] running record has no pid; aborting switch")
            raise typer.Exit(code=1)
        try:
            os.kill(rec.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_pid_gone(rec.pid, timeout_s=10.0):
            try:
                os.kill(rec.pid, _SIGKILL)
            except ProcessLookupError:
                pass
        clear_running(repo)
        append_history(
            repo,
            {
                "action": "switch",
                "mode": "background",
                "from": old_id,
                "to": config_id,
            },
        )
        _do_background(settings, new_for_env, repo, env)
        return

    if rec.mode == "systemd":
        clear_running(repo)
        append_history(
            repo,
            {
                "action": "switch",
                "mode": "systemd",
                "from": old_id,
                "to": config_id,
            },
        )
        _do_systemd(settings, new_for_env, repo, env)
        return

    console.print(f"[red]error:[/red] unknown mode {rec.mode!r}")
    raise typer.Exit(code=1)
