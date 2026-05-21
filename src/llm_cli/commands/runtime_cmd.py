"""`loco runtime` - manage runtime installs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.commands.runtime_setup import (
    interactive_runtime_setup,
    last_runtime_setup_id,
    run_install_for_id as _run_install_for_id,
)
from llm_cli.core import registry
from llm_cli.core.install_record import (
    InstallRecord,
    clear_record,
    file_sha256,
    is_installed,
    read_record,
    schema_hash,
    write_record,
)
from llm_cli.core.lifecycle import append_history, state_root
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core import runtime_install as rt_install
from llm_cli.core.runtime_install import RuntimeInstallError

console = Console()
runtime_app = typer.Typer(
    help="Manage runtime installs (list/info/install/uninstall/rebuild)."
)

def _settings() -> Settings:
    return resolve(load_settings())


def _get_runtime_manifest(runtime_id: str) -> registry.RuntimeManifest:
    manifest = registry.get_runtime_manifest_merged(runtime_id)
    if manifest is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    return manifest


def _install_impl(
    *,
    settings: Settings,
    runtime_id: str,
    param: list[str],
    yes: bool,
) -> InstallRecord:
    try:
        return rt_install.install_runtime(
            runtime_id, param=list(param), yes=yes, settings=settings
        )
    except RuntimeInstallError as exc:
        console.print(f"[red]error:[/red] {exc.message}")
        raise typer.Exit(code=exc.exit_code) from exc


@runtime_app.command("setup", help="Interactive wizard to install or register a runtime.")
def runtime_setup_command() -> None:
    try:
        rid = interactive_runtime_setup()
    except typer.Exit:
        raise
    if rid is None:
        console.print("[yellow]aborted[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]done[/green] runtime {rid}")


@runtime_app.command("list", help="List runtimes with install state.")
def runtime_list(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    settings = _settings()
    manifests = registry.load_runtime_manifests_merged()

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
    settings = _settings()
    manifest = _get_runtime_manifest(runtime_id)
    rec = registry.get_runtime_merged(runtime_id)

    console.print(f"[bold]{manifest.id}[/bold] - {manifest.display_name}")
    if rec is not None:
        console.print(f"source: {rec.source}")
    console.print(f"official: {'yes' if manifest.official else 'no'}")
    if manifest.description:
        console.print(f"description: {manifest.description}")

    if manifest.build_schema:
        console.print("\n[bold]build params:[/bold]")
        for spec in manifest.build_schema:
            line = f"  - {spec.key} ({spec.type.value})"
            if spec.required:
                line += " required"
            console.print(line)

    if manifest.serve_schema:
        console.print("\n[bold]serve params:[/bold]")
        for spec in manifest.serve_schema:
            line = f"  - {spec.key} ({spec.type.value})"
            if spec.required:
                line += " required"
            console.print(line)

    record = read_record(settings.runtimes_dir, manifest.id)
    if record is None:
        console.print("\n[yellow]not installed[/yellow]")
        console.print(f"hint: loco runtime install {manifest.id}")
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
            f"run `loco runtime rebuild {manifest.id} --reset` to refresh"
        )


@runtime_app.command("install", help="Install a runtime.")
def runtime_install(
    runtime_id: str = typer.Argument(...),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults; skip prompts."),
) -> None:
    settings = _settings()
    record = _install_impl(
        settings=settings, runtime_id=runtime_id, param=list(param), yes=yes
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
        from llm_cli.core import wizards as wiz

        if not wiz.confirm(prompt, default=False):
            console.print("aborted")
            raise typer.Exit(code=1)

    clear_record(settings.runtimes_dir, runtime_id)
    if purge and runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    append_history(
        state_root(settings),
        {"action": "runtime-uninstall", "id": runtime_id, "purge": purge},
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
    settings = _settings()
    mf = registry.get_runtime_manifest_merged(runtime_id)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    if mf.kind == "custom":
        console.print(
            f"[red]error:[/red] rebuild applies to official runtimes only "
            f"({runtime_id!r} is kind: custom)"
        )
        raise typer.Exit(code=1)

    try:
        new_record = rt_install.rebuild_runtime(
            runtime_id,
            reset=reset,
            param=list(param),
            yes=yes,
            settings=settings,
        )
    except RuntimeInstallError as exc:
        console.print(f"[red]error:[/red] {exc.message}")
        raise typer.Exit(code=exc.exit_code) from exc
    summary = ", ".join(f"{k}={v}" for k, v in new_record.build_params.items())
    console.print(f"[green]rebuilt[/green] {runtime_id} ({summary or 'no params'})")
