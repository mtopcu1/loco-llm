"""CLI presentation helpers for serve/switch."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.core.serve_errors import ServeError

console = Console()


def serve_status_message(message: str) -> None:
    """Rich formatter passed to ``core.serve`` as ``on_message``."""
    if message.startswith("running "):
        console.print(f"[green]running[/green] {message[8:]}")
        return
    if message.startswith("already serving "):
        console.print(f"[green]already serving[/green] {message[16:]}")
        return
    console.print(f"[green]{message}[/green]")


def raise_serve_exit(exc: ServeError) -> None:
    console.print(f"[red]error:[/red] {exc.message}")
    if exc.hint:
        console.print(exc.hint)
    raise typer.Exit(code=exc.exit_code) from exc
