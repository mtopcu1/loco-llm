"""Canonical runtime install and rebuild (CLI and dashboard API)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_cli.core import registry
from llm_cli.core.doctor import CheckStatus, check_all, requirements_for_runtime
from llm_cli.core.install_record import (
    InstallRecord,
    clear_record,
    file_sha256,
    read_record,
    schema_hash,
    write_record,
)
from llm_cli.core.lifecycle import append_history, state_root
from llm_cli.core.params import derive_env_name, validate_params
from llm_cli.core.repo import scaffold_root
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core.time import utc_now_iso
from llm_cli.core.wsl import run_runtime_bash


class RuntimeInstallError(Exception):
    """Runtime install/rebuild failed."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


def default_build_param_tokens(runtime_id: str) -> list[str]:
    """Dashboard/API defaults for official runtime install flags."""
    if runtime_id == "vllm":
        return ["vllm_version=0.21.0", "pip_extra=cuda"]
    return []


def _parse_param_token(token: str) -> tuple[str, str]:
    from llm_cli.core.params import ParamTokenError, parse_cli_param_token

    try:
        return parse_cli_param_token(token)
    except ParamTokenError as exc:
        raise RuntimeInstallError(str(exc)) from exc


def _resolve_build_params(
    runtime_id: str,
    schema: list[Any],
    *,
    flags: list[str],
    yes: bool,
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for token in flags:
        key, value = _parse_param_token(token)
        raw[key] = value

    if not yes and schema:
        from llm_cli.core import wizards as wiz

        pre_values = {k: str(v) for k, v in raw.items()}
        result = wiz.edit_params(
            schema,
            title=f"Build params: {runtime_id}",
            values=pre_values,
        )
        if result.action == "abort":
            raise RuntimeInstallError("aborted", exit_code=1)
        raw.update(result.values)

    coerced, errors = validate_params(schema, raw)
    if errors:
        raise RuntimeInstallError("; ".join(str(e) for e in errors))
    return coerced


def _build_env(
    runtime_id: str, schema: list[Any], build_params: dict[str, Any]
) -> dict[str, str]:
    env: dict[str, str] = {}
    for spec in schema:
        if spec.key not in build_params:
            continue
        name = derive_env_name(spec, runtime_id=runtime_id, scope="build")
        env[name] = str(build_params[spec.key])
    return env


def _run_build_script(
    *,
    settings: Settings,
    runtime_path: Path,
    env: dict[str, str],
) -> int:
    return run_runtime_bash(settings, runtime_path, "build.sh", extra_env=env)


def _run_verify_script(
    *,
    settings: Settings,
    runtime_path: Path,
    env: dict[str, str],
) -> int | None:
    if not (runtime_path / "verify.sh").is_file():
        return None
    return run_runtime_bash(settings, runtime_path, "verify.sh", extra_env=env)


def _pre_flight(runtime_id: str, build_params: dict[str, Any]) -> None:
    scaffold = scaffold_root()
    requirements = requirements_for_runtime(scaffold, runtime_id, build_params=build_params)
    if not requirements:
        return
    results = check_all(requirements)
    bad = [r for r in results if r.status is not CheckStatus.OK]
    if not bad:
        return
    lines = [
        f"{result.requirement.id} ({result.status.value}): "
        f"{result.requirement.install_hint or 'install manually'}"
        for result in bad
    ]
    raise RuntimeInstallError("missing requirements: " + "; ".join(lines))


def install_runtime(
    runtime_id: str,
    *,
    param: list[str] | None = None,
    yes: bool = True,
    settings: Settings | None = None,
) -> InstallRecord:
    """Install a runtime after validating build params and running build/verify scripts."""
    settings = resolve(load_settings()) if settings is None else settings
    manifest = registry.get_runtime_manifest_merged(runtime_id)
    if manifest is None:
        raise RuntimeInstallError(f"unknown runtime {runtime_id!r}")
    runtime_rec = registry.get_runtime_merged(runtime_id)
    if runtime_rec is None:
        raise RuntimeInstallError(f"unknown runtime {runtime_id!r}")
    if manifest.kind == "custom":
        raise RuntimeInstallError(
            f"runtime {runtime_id!r} is kind: custom — it has no build step. "
            "Use `loco runtime setup` to re-register or edit files under "
            f"{manifest.path}."
        )

    flags = list(param or [])
    build_params = _resolve_build_params(
        runtime_id, manifest.build_schema, flags=flags, yes=yes
    )
    _pre_flight(runtime_id, build_params)

    build_env = _build_env(runtime_id, manifest.build_schema, build_params)
    build_rc = _run_build_script(
        settings=settings, runtime_path=runtime_rec.path, env=build_env
    )
    if build_rc != 0:
        raise RuntimeInstallError(f"build failed (exit {build_rc})", exit_code=build_rc)

    verify_rc = _run_verify_script(
        settings=settings, runtime_path=runtime_rec.path, env=build_env
    )
    if verify_rc not in (None, 0):
        raise RuntimeInstallError(f"verify failed (exit {verify_rc})", exit_code=verify_rc)

    record = InstallRecord(
        runtime_id=runtime_id,
        installed_at=utc_now_iso(),
        build_params=build_params,
        build_sh_sha256=file_sha256(manifest.path / "build.sh"),
        verify_passed=True if verify_rc == 0 else None,
        schema_hash=schema_hash(manifest.raw.get("build") or {}),
        kind=manifest.kind,
    )
    write_record(settings.runtimes_dir, record)
    append_history(
        state_root(settings),
        {
            "action": "runtime-install",
            "id": runtime_id,
            "build_params": build_params,
        },
    )
    return record


def rebuild_runtime(
    runtime_id: str,
    *,
    reset: bool = False,
    param: list[str] | None = None,
    yes: bool = True,
    settings: Settings | None = None,
) -> InstallRecord:
    """Reinstall a runtime; reuse stored build params unless ``reset``."""
    settings = resolve(load_settings()) if settings is None else settings
    manifest = registry.get_runtime_manifest_merged(runtime_id)
    if manifest is None:
        raise RuntimeInstallError(f"unknown runtime {runtime_id!r}")
    if manifest.kind == "custom":
        raise RuntimeInstallError(
            f"rebuild applies to official runtimes only ({runtime_id!r} is kind: custom)"
        )

    record = read_record(settings.runtimes_dir, runtime_id)
    flags: list[str] = []
    if record is not None and not reset:
        flags.extend(f"{key}={value}" for key, value in record.build_params.items())
    flags.extend(param or [])

    clear_record(settings.runtimes_dir, runtime_id)
    new_record = install_runtime(
        runtime_id, param=flags, yes=yes, settings=settings
    )
    append_history(
        state_root(settings),
        {"action": "runtime-rebuild", "id": runtime_id, "reset": reset},
    )
    return new_record
