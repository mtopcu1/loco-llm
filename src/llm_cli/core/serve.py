"""Canonical serve/switch implementation (CLI and dashboard API)."""
from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from llm_cli.core import registry
from llm_cli.core.serve_errors import ServeError
from llm_cli.core.install_record import is_installed
from llm_cli.core.lifecycle import (
    append_history,
    clear_running,
    read_running,
    reconcile,
    state_root,
)
from llm_cli.core.repo import scaffold_root
from llm_cli.core.serve_modes import (
    ServeMessageFn,
    ServeStartContext,
    MODE_STARTERS,
    start_background,
    start_foreground,
    start_systemd,
)
from llm_cli.core.serve_spawn import (
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
# Windows' `signal` module has no SIGKILL; POSIX uses 9.
_SIGKILL = int(getattr(signal, "SIGKILL", 9))

if TYPE_CHECKING:
    from llm_cli.core.registry import ConfigRecord


def _fail(message: str, *, hint: str | None = None, code: int = 1) -> NoReturn:
    raise ServeError(message, exit_code=code, hint=hint)


def _resolve_cfg(config_id: str) -> "ConfigRecord":
    cfg = registry.get_config_merged(config_id)
    if cfg is None:
        _fail(f"unknown config {config_id!r}")
    errs = registry.validate_config(scaffold_root(), cfg)
    if errs:
        _fail("; ".join(str(e) for e in errs))
    return cfg


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


def _start_context(
    settings: Settings,
    cfg: "ConfigRecord",
    state_base: Path,
    env: dict[str, str],
    runtime_path: Path,
    *,
    on_message: ServeMessageFn = None,
    from_supervisor: bool = False,
) -> ServeStartContext:
    return ServeStartContext(
        settings=settings,
        cfg=cfg,
        state_base=state_base,
        env=env,
        runtime_path=runtime_path,
        on_message=on_message,
        from_supervisor=from_supervisor,
    )


def serve_dispatch(
    config_id: str,
    *,
    foreground: bool = False,
    systemd: bool = False,
    foreground_from_supervisor: bool = False,
    on_message: ServeMessageFn = None,
) -> None:
    """Start a config in foreground, background, or systemd mode (raises ServeError)."""
    _serve_dispatch_impl(
        config_id,
        foreground=foreground,
        systemd=systemd,
        foreground_from_supervisor=foreground_from_supervisor,
        on_message=on_message,
    )


def _serve_dispatch_impl(
    config_id: str,
    *,
    foreground: bool = False,
    systemd: bool = False,
    foreground_from_supervisor: bool = False,
    on_message: ServeMessageFn = None,
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
        if on_message is not None:
            on_message(f"already serving {config_id} via systemd")
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

    ctx = _start_context(
        settings,
        cfg_for_env,
        state_base,
        env,
        runtime_path,
        on_message=on_message,
        from_supervisor=foreground_from_supervisor,
    )
    if foreground or foreground_from_supervisor:
        start_foreground(ctx)
    elif systemd:
        start_systemd(ctx)
    else:
        start_background(ctx)


def switch_impl(config_id: str, *, on_message: ServeMessageFn = None) -> None:
    """Stop the running service and start another config in the same mode."""
    _switch_impl_body(config_id, on_message=on_message)


def _switch_impl_body(
    config_id: str,
    *,
    on_message: ServeMessageFn = None,
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
        from llm_cli.core.process_control import stop_background_pid

        stop_background_pid(rec.pid)
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
        starter = MODE_STARTERS.get("background")
        if starter is None:
            _fail(f"unknown mode {rec.mode!r}")
        starter(
            _start_context(
                settings,
                new_for_env,
                state_base,
                env,
                runtime_path,
                on_message=on_message,
            )
        )
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
        start_systemd(
            _start_context(
                settings,
                new_for_env,
                state_base,
                env,
                runtime_path,
                on_message=on_message,
            )
        )
        return

    _fail(f"unknown mode {rec.mode!r}")
