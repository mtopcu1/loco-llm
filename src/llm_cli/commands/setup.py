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
    stored: dict[str, str] = {"repo_root": str(repo_root)}

    if default:
        stored["data_root"] = _default_data_root()
    else:
        stored["data_root"] = typer.prompt(
            KEY_REGISTRY["data_root"]["prompt"],
            default=_default_data_root(),
        )
        granular = typer.confirm(
            "Use default subdirectory layout under data_root?",
            default=True,
        )
        if not granular:
            stored.update(_prompt_dir_overrides(stored["data_root"]))

    path = save_settings(stored)
    resolved = resolve(load_settings())
    ensure_data_dirs(resolved)
    console.print(f"[green]wrote[/green] {path}")
    console.print(f"[green]data_root[/green]: {resolved.data_root}")
    console.print(f"[green]runtimes_dir[/green]: {resolved.runtimes_dir}")
    console.print(f"[green]models_dir[/green]: {resolved.models_dir}")
    console.print(f"[green]cache_dir[/green]: {resolved.cache_dir}")
    console.print(f"[green]repo_root[/green]: {resolved.repo_root}")


def _prompt_dir_overrides(data_root: str) -> dict[str, str]:
    """Placeholder; granular prompts are added in Task 10."""
    return {}
