"""`llm model` — list/info/pull/add/uninstall against $LLM_MODELS/registry.json."""
from __future__ import annotations

import json as _json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.model_registry import encode_entry, get_entry, load_registry
from llm_cli.core.settings import load_settings, resolve

console = Console()
model_app = typer.Typer(help="Manage models (list/info/pull/add/uninstall).")


def _models_dir() -> Path:
    return resolve(load_settings()).models_dir


@model_app.command("list", help="List models registered in $LLM_MODELS/registry.json.")
def model_list(as_json: bool = typer.Option(False, "--json")) -> None:
    models_dir = _models_dir()
    reg = load_registry(models_dir)
    if as_json:
        typer.echo(
            _json.dumps({k: encode_entry(v) for k, v in reg.items()}, indent=2)
        )
        return
    if not reg:
        console.print("[dim]no models registered[/dim]")
        return
    table = Table(title="Models")
    table.add_column("ID")
    table.add_column("Format")
    table.add_column("Source")
    table.add_column("Size")
    table.add_column("Present")
    for mid, e in sorted(reg.items()):
        present = (models_dir / mid / e.artifact.primary).exists()
        table.add_row(
            mid,
            e.format,
            e.source.kind,
            f"{e.artifact.total_size_bytes}",
            "yes" if present else "[red]no[/red]",
        )
    console.print(table)


@model_app.command("info", help="Show a registered model's full entry.")
def model_info(
    model_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    models_dir = _models_dir()
    e = get_entry(models_dir, model_id)
    if e is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    if as_json:
        typer.echo(_json.dumps({model_id: encode_entry(e)}, indent=2))
        return
    console.print(f"[bold]{e.id}[/bold] — {e.metadata.display_name or '(no display name)'}")
    console.print(f"  format: {e.format}")
    console.print(f"  source.kind: {e.source.kind}")
    if hasattr(e.source, "repo"):
        console.print(f"  source.repo: {e.source.repo}@{e.source.revision}")
        if e.source.include:
            console.print(f"  source.include: {list(e.source.include)}")
    if hasattr(e.source, "original_path"):
        console.print(f"  source.original_path: {e.source.original_path}")
    console.print(f"  artifact.primary: {e.artifact.primary}")
    console.print(
        f"  artifact.files: {len(e.artifact.files)} file(s), "
        f"{e.artifact.total_size_bytes} bytes"
    )
    if e.metadata.license:
        console.print(f"  metadata.license: {e.metadata.license}")
    if e.metadata.ctx_length:
        console.print(f"  metadata.ctx_length: {e.metadata.ctx_length}")
    console.print(f"  installed_at: {e.installed_at}")
