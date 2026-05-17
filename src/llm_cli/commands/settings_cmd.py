"""`llm settings ...` - inspect and edit user-level settings."""
from __future__ import annotations

import shlex

import typer
from rich.console import Console

from llm_cli.core.settings import KEY_REGISTRY, load_settings, resolve, settings_path

console = Console(soft_wrap=True)

settings_app = typer.Typer(help="Inspect and edit user-level settings.")

_ENV_MAPPING = (
    ("LLM_DATA_ROOT", "data_root"),
    ("LLM_REPO_ROOT", "repo_root"),
    ("LLM_RUNTIMES", "runtimes_dir"),
    ("LLM_MODELS", "models_dir"),
    ("LLM_CACHE", "cache_dir"),
)


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


@settings_app.command("env")
def env() -> None:
    """Print `export LLM_*=...` lines for `eval "$(llm settings env)"`."""
    resolved = resolve(load_settings())
    for var, attr in _ENV_MAPPING:
        value = getattr(resolved, attr).as_posix()
        typer.echo(f"export {var}={shlex.quote(value)}")
