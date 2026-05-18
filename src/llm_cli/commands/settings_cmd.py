"""`llm settings ...` - inspect and edit user-level settings."""
from __future__ import annotations

import shlex

import typer
from rich.console import Console

from llm_cli.core.settings import (
    KEY_REGISTRY,
    ensure_data_dirs,
    load_settings,
    resolve,
    save_settings,
    settings_path,
)

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
        val = getattr(resolved, key)
        if val is None:
            console.print(f"  {key}: (not set)")
        else:
            console.print(f"  {key}: {val}")


@settings_app.command("env")
def env() -> None:
    """Print `export LLM_*=...` lines for `eval "$(llm settings env)"`."""
    resolved = resolve(load_settings())
    for var, attr in _ENV_MAPPING:
        val = getattr(resolved, attr)
        if attr == "repo_root" and val is None:
            from llm_cli.core.repo import scaffold_root

            value = scaffold_root().as_posix()
        elif val is None:
            continue
        else:
            value = val.as_posix()
        typer.echo(f"export {var}={shlex.quote(value)}")


@settings_app.command("edit")
def edit(
    key: str = typer.Argument(..., help="Setting key to edit."),
    default: bool = typer.Option(
        False, "--default", help="Reset key to its built-in default."
    ),
) -> None:
    """Edit a single settings key, interactively by default."""
    if key not in KEY_REGISTRY:
        console.print(
            f"[red]error:[/red] unknown setting {key!r}. "
            f"Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
        raise typer.Exit(code=1)

    stored = load_settings()
    meta = KEY_REGISTRY[key]

    if default:
        if meta.get("required") and meta.get("default") is None:
            console.print(
                f"[red]error:[/red] {key!r} has no built-in default; "
                f"use `llm settings edit {key}` to set a new value."
            )
            raise typer.Exit(code=1)
        if meta["default"] is None:
            stored.pop(key, None)
        else:
            stored[key] = meta["default"]
    else:
        current = stored.get(key) or meta.get("default") or ""
        answer = typer.prompt(meta["prompt"], default=current).strip()
        if answer:
            stored[key] = answer
        else:
            stored.pop(key, None)

    save_settings(stored)
    resolved = resolve(stored)
    ensure_data_dirs(resolved)
    console.print(f"[green]updated[/green] {key}")
