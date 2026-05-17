"""`llm settings ...` - inspect and edit user-level settings."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.core.settings import KEY_REGISTRY, load_settings, resolve, settings_path

console = Console(soft_wrap=True)

settings_app = typer.Typer(help="Inspect and edit user-level settings.")


@settings_app.command("show")
def show() -> None:
    """Print the settings file path, stored contents, and resolved view."""
    path = settings_path()
    stored = load_settings()
    console.print(f"[bold]file[/bold]: {path}")
    console.print("[bold]stored[/bold]:")
    if stored:
        for key in KEY_REGISTRY:
            if key in stored:
                console.print(f"  {key}: {stored[key]}")
    else:
        console.print("  (empty)")
    console.print("[bold]resolved[/bold]:")
    resolved = resolve(stored)
    for key in KEY_REGISTRY:
        console.print(f"  {key}: {getattr(resolved, key)}")
