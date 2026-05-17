"""`llm runtime` - manage runtime installs."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core import registry
from llm_cli.core.doctor import CheckStatus, check_all, requirements_for_runtime
from llm_cli.core.install_record import (
    InstallRecord,
    clear_record,
    file_sha256,
    is_installed,
    read_record,
    schema_hash,
    write_record,
)
from llm_cli.core.lifecycle import append_history
from llm_cli.core.params import derive_env_name, validate_params
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core.wsl import run_repo_bash

console = Console()
runtime_app = typer.Typer(
    help="Manage runtime installs (list/info/install/uninstall/rebuild)."
)


def _settings() -> Settings:
    return resolve(load_settings())


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_param_flag(token: str) -> tuple[str, str]:
    if "=" not in token:
        raise typer.BadParameter(f"--param must be key=value (got {token!r})")
    key, value = token.split("=", 1)
    key = key.strip()
    if not key:
        raise typer.BadParameter("--param key cannot be empty")
    return key, value.strip()


def _resolve_build_params(
    schema: list[Any], *, flags: list[str], yes: bool
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for token in flags:
        key, value = _parse_param_flag(token)
        raw[key] = value

    for spec in schema:
        if spec.key in raw:
            continue
        if yes:
            continue
        prompt = spec.prompt or spec.key
        if spec.default is None:
            raw[spec.key] = typer.prompt(prompt)
        else:
            raw[spec.key] = typer.prompt(prompt, default=str(spec.default))

    coerced, errors = validate_params(schema, raw)
    if errors:
        for error in errors:
            console.print(f"[red]error:[/red] {error}")
        raise typer.Exit(code=1)
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
    repo: Path,
    runtime_id: str,
    env: dict[str, str],
) -> int:
    """Run runtimes/<id>/build.sh via repo bash; patch point for tests."""
    return run_repo_bash(
        settings,
        f"runtimes/{runtime_id}/build.sh",
        extra_env=env,
    )


def _run_verify_script(
    *,
    settings: Settings,
    repo: Path,
    runtime_id: str,
    env: dict[str, str],
) -> int | None:
    """Run runtimes/<id>/verify.sh if present; patch point for tests."""
    if not (repo / "runtimes" / runtime_id / "verify.sh").is_file():
        return None
    return run_repo_bash(
        settings,
        f"runtimes/{runtime_id}/verify.sh",
        extra_env=env,
    )


def _pre_flight(repo: Path, runtime_id: str, build_params: dict[str, Any]) -> None:
    requirements = requirements_for_runtime(repo, runtime_id, build_params=build_params)
    if not requirements:
        return

    results = check_all(requirements)
    bad = [r for r in results if r.status is not CheckStatus.OK]
    if not bad:
        return

    for result in bad:
        hint = result.requirement.install_hint or "install manually"
        console.print(
            f"[red]missing:[/red] {result.requirement.id} "
            f"({result.status.value}). hint: {hint}"
        )
    raise typer.Exit(code=1)


def _get_runtime_manifest(repo: Path, runtime_id: str) -> registry.RuntimeManifest:
    manifest = registry.get_runtime_manifest(repo, runtime_id)
    if manifest is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    return manifest


def _install_impl(
    *,
    repo: Path,
    settings: Settings,
    runtime_id: str,
    param: list[str],
    yes: bool,
) -> InstallRecord:
    manifest = _get_runtime_manifest(repo, runtime_id)
    build_params = _resolve_build_params(manifest.build_schema, flags=param, yes=yes)
    _pre_flight(repo, runtime_id, build_params)

    build_env = _build_env(runtime_id, manifest.build_schema, build_params)
    build_rc = _run_build_script(
        settings=settings, repo=repo, runtime_id=runtime_id, env=build_env
    )
    if build_rc != 0:
        console.print(f"[red]build failed[/red] (exit {build_rc})")
        raise typer.Exit(code=build_rc)

    verify_rc = _run_verify_script(
        settings=settings, repo=repo, runtime_id=runtime_id, env=build_env
    )
    if verify_rc not in (None, 0):
        console.print(f"[red]verify failed[/red] (exit {verify_rc})")
        raise typer.Exit(code=verify_rc)

    record = InstallRecord(
        runtime_id=runtime_id,
        installed_at=_utc_now_iso(),
        build_params=build_params,
        build_sh_sha256=file_sha256(manifest.path / "build.sh"),
        verify_passed=True if verify_rc == 0 else None,
        schema_hash=schema_hash(manifest.raw.get("build") or {}),
    )
    write_record(settings.runtimes_dir, record)
    append_history(
        repo,
        {
            "action": "runtime-install",
            "id": runtime_id,
            "build_params": build_params,
        },
    )
    return record


@runtime_app.command("list", help="List runtimes with install state.")
def runtime_list(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    repo = repo_root()
    settings = _settings()
    manifests = registry.load_runtime_manifests(repo)

    rows: list[dict[str, Any]] = []
    for manifest in manifests:
        record = read_record(settings.runtimes_dir, manifest.id)
        rows.append(
            {
                "id": manifest.id,
                "display_name": manifest.display_name,
                "official": manifest.official,
                "installed": record is not None,
                "installed_at": record.installed_at if record else None,
                "build_params": dict(record.build_params) if record else None,
            }
        )

    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return

    table = Table(title="Runtimes")
    table.add_column("ID")
    table.add_column("Display")
    table.add_column("Official")
    table.add_column("Installed")
    table.add_column("Build params")
    for row in rows:
        build_params = row["build_params"]
        params_text = (
            ", ".join(f"{k}={v}" for k, v in build_params.items())
            if build_params
            else "-"
        )
        table.add_row(
            row["id"],
            row["display_name"],
            "yes" if row["official"] else "no",
            "yes" if row["installed"] else "no",
            params_text,
        )
    console.print(table)


@runtime_app.command("info", help="Show manifest, install record, and drift.")
def runtime_info(runtime_id: str = typer.Argument(...)) -> None:
    repo = repo_root()
    settings = _settings()
    manifest = _get_runtime_manifest(repo, runtime_id)

    console.print(f"[bold]{manifest.id}[/bold] - {manifest.display_name}")
    console.print(f"official: {'yes' if manifest.official else 'no'}")
    if manifest.description:
        console.print(f"description: {manifest.description}")

    if manifest.build_schema:
        console.print("\n[bold]build params:[/bold]")
        for spec in manifest.build_schema:
            line = f"  - {spec.key} ({spec.type.value})"
            if spec.default is not None:
                line += f" default={spec.default!r}"
            if spec.required:
                line += " required"
            console.print(line)

    if manifest.serve_schema:
        console.print("\n[bold]serve params:[/bold]")
        for spec in manifest.serve_schema:
            line = f"  - {spec.key} ({spec.type.value})"
            if spec.default is not None:
                line += f" default={spec.default!r}"
            if spec.required:
                line += " required"
            console.print(line)

    record = read_record(settings.runtimes_dir, manifest.id)
    if record is None:
        console.print("\n[yellow]not installed[/yellow]")
        console.print(f"hint: llm runtime install {manifest.id}")
        return

    console.print("\n[bold]install:[/bold] [green]installed[/green]")
    console.print(f"installed_at: {record.installed_at}")
    console.print(f"verify_passed: {record.verify_passed}")
    if record.build_params:
        params = ", ".join(f"{k}={v}" for k, v in record.build_params.items())
        console.print(f"build_params: {params}")

    current_sha = file_sha256(manifest.path / "build.sh")
    if record.build_sh_sha256 and current_sha and current_sha != record.build_sh_sha256:
        console.print(
            "[yellow]drift:[/yellow] build.sh has changed since install "
            f"({record.build_sh_sha256[:8]} -> {current_sha[:8]})"
        )

    current_schema = schema_hash(manifest.raw.get("build") or {})
    if record.schema_hash and current_schema and current_schema != record.schema_hash:
        console.print(
            "[yellow]drift:[/yellow] build schema changed since install; "
            f"run `llm runtime rebuild {manifest.id} --reset` to refresh"
        )


@runtime_app.command("install", help="Install a runtime.")
def runtime_install(
    runtime_id: str = typer.Argument(...),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults; skip prompts."),
) -> None:
    repo = repo_root()
    settings = _settings()
    record = _install_impl(
        repo=repo, settings=settings, runtime_id=runtime_id, param=list(param), yes=yes
    )
    summary = ", ".join(f"{k}={v}" for k, v in record.build_params.items())
    console.print(f"[green]installed[/green] {runtime_id} ({summary or 'no params'})")


@runtime_app.command(
    "uninstall", help="Remove a runtime's install marker and optionally artifacts."
)
def runtime_uninstall(
    runtime_id: str = typer.Argument(...),
    purge: bool = typer.Option(False, "--purge", help="Also delete the install directory."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompts."),
) -> None:
    repo = repo_root()
    settings = _settings()
    runtime_dir = settings.runtimes_dir / runtime_id

    if not is_installed(settings.runtimes_dir, runtime_id):
        console.print(
            f"[yellow]nothing to uninstall:[/yellow] {runtime_id} is not installed"
        )
        if not purge or not runtime_dir.exists():
            return

    if not yes:
        prompt = (
            f"Purge {runtime_dir}? (all build artifacts will be deleted)"
            if purge
            else f"Remove install marker for {runtime_id}?"
        )
        if not typer.confirm(prompt, default=False):
            console.print("aborted")
            raise typer.Exit(code=1)

    clear_record(settings.runtimes_dir, runtime_id)
    if purge and runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    append_history(
        repo, {"action": "runtime-uninstall", "id": runtime_id, "purge": purge}
    )
    console.print(
        f"[green]uninstalled[/green] {runtime_id}" + (" (purged)" if purge else "")
    )


@runtime_app.command(
    "rebuild", help="Reinstall a runtime; reuse stored build params unless --reset."
)
def runtime_rebuild(
    runtime_id: str = typer.Argument(...),
    reset: bool = typer.Option(False, "--reset", help="Discard stored params."),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults; skip prompts."),
) -> None:
    repo = repo_root()
    settings = _settings()
    record = read_record(settings.runtimes_dir, runtime_id)

    flags: list[str] = []
    if record is not None and not reset:
        flags.extend(f"{key}={value}" for key, value in record.build_params.items())
    flags.extend(param)

    clear_record(settings.runtimes_dir, runtime_id)
    new_record = _install_impl(
        repo=repo, settings=settings, runtime_id=runtime_id, param=flags, yes=yes
    )
    append_history(
        repo, {"action": "runtime-rebuild", "id": runtime_id, "reset": reset}
    )
    summary = ", ".join(f"{k}={v}" for k, v in new_record.build_params.items())
    console.print(f"[green]rebuilt[/green] {runtime_id} ({summary or 'no params'})")
