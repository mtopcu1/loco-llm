"""`llm setup` — first-run interactive configurator."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.settings import (
    KEY_REGISTRY,
    ensure_data_dirs,
    load_settings,
    resolve,
    save_settings,
)

console = Console()


def _default_data_root() -> str:
    return os.environ.get(
        "LLM_DEFAULT_DATA_ROOT", KEY_REGISTRY["data_root"]["default"]
    )


def setup(
    default: bool = typer.Option(
        False, "--default", help="Non-interactive: use defaults for every key."
    ),
) -> None:
    """Configure machine-local settings (~/.config/llm/config.yaml)."""
    repo_root = Path.cwd().resolve()
    data_root = _default_data_root()
    stored = {"data_root": data_root, "repo_root": str(repo_root)}

    if not default:
        console.print(
            "[yellow]interactive setup not yet implemented; "
            "re-run with --default[/yellow]"
        )
        raise typer.Exit(code=2)

    path = save_settings(stored)
    resolved = resolve(load_settings())
    ensure_data_dirs(resolved)
    console.print(f"[green]wrote[/green] {path}")
    console.print(f"[green]data_root[/green]: {resolved.data_root}")
    console.print(f"[green]repo_root[/green]: {resolved.repo_root}")
