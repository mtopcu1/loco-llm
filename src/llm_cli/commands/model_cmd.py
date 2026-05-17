"""`llm model` — list/info/pull model definitions."""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core import registry
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.wsl import run_repo_bash

console = Console()
model_app = typer.Typer(help="Manage models (list/info/pull).")


@model_app.command("list", help="List models discovered in the repo.")
def model_list(as_json: bool = typer.Option(False, "--json")) -> None:
    repo = repo_root()
    rows = [
        {
            "id": m.id,
            "display_name": str(m.manifest.get("display_name", m.id)),
            "source_kind": str((m.manifest.get("source") or {}).get("kind", "")),
        }
        for m in registry.discover_models(repo)
    ]
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    table = Table(title="Models")
    table.add_column("ID")
    table.add_column("Display")
    table.add_column("Source")
    for r in rows:
        table.add_row(r["id"], r["display_name"], r["source_kind"] or "-")
    console.print(table)


@model_app.command("info", help="Show a model's manifest details.")
def model_info(model_id: str = typer.Argument(...)) -> None:
    repo = repo_root()
    md = registry.get_model(repo, model_id)
    if md is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    console.print(f"[bold]{md.id}[/bold] — {md.manifest.get('display_name', md.id)}")
    src = md.manifest.get("source") or {}
    if src:
        for k, v in src.items():
            console.print(f"  source.{k}: {v}")
    if md.manifest.get("description"):
        console.print(f"description: {md.manifest['description']}")


@model_app.command("pull", help="Run models/<id>/pull.sh in WSL with LLM_* env injected.")
def model_pull(model_id: str = typer.Argument(...)) -> None:
    repo = repo_root()
    md = registry.get_model(repo, model_id)
    if md is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    rc = run_repo_bash(settings, f"models/{model_id}/pull.sh")
    if rc != 0:
        console.print(f"[red]pull failed[/red] (exit {rc})")
        raise typer.Exit(code=rc)
