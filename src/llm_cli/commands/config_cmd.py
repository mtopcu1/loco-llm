"""`llm config` — show and validate configuration files."""
from __future__ import annotations

import json

import typer
import yaml
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve

console = Console()

config_app = typer.Typer(help="Inspect and validate configs/*.yaml.")


@config_app.command("show")
def config_show(
    config_id: str = typer.Argument(..., help="Config id (filename stem)."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of YAML."),
) -> None:
    """Print a single resolved config (expands ${data_root} in serve.env)."""
    repo = repo_root()
    cfg = registry.get_config(repo, config_id)
    if cfg is None:
        console.print(f"[red]error:[/red] unknown config {config_id!r}")
        raise typer.Exit(code=1)
    resolved = resolve_config_for_display(cfg, resolve(load_settings()))
    if as_json:
        typer.echo(json.dumps(resolved, indent=2))
    else:
        typer.echo(yaml.safe_dump(resolved, sort_keys=False, allow_unicode=True))


@config_app.command("validate")
def config_validate() -> None:
    """Validate every configs/*.yaml against repo manifests and script layout."""
    repo = repo_root()
    configs = registry.discover_configs(repo)
    if not configs:
        console.print("[yellow]warning:[/yellow] no configs/*.yaml found")
        raise typer.Exit(code=0)

    bad = 0
    for cfg in configs:
        errors, warnings = registry.validate_config_v2(repo, cfg)
        if errors:
            bad += 1
            console.print(f"[red]{cfg.id}[/red]")
            for e in errors:
                console.print(f"  - {e}")
        else:
            console.print(f"[green]ok[/green] {cfg.id}")
        for w in warnings:
            console.print(f"[yellow]warning:[/yellow] {w}")

    if bad:
        raise typer.Exit(code=1)
