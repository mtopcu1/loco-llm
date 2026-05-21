"""`loco serve` and `loco switch` — Typer wrappers around core.serve."""
from __future__ import annotations

import typer

from llm_cli.commands.serve_io import raise_serve_exit, serve_status_message
from llm_cli.core.serve import (
    _serve_env_from_params,
    serve_dispatch,
    switch_impl,
)
from llm_cli.core.serve_errors import ServeError

# Backward-compatible alias for callers that imported the private name.
_switch_impl = switch_impl

__all__ = [
    "_serve_env_from_params",
    "_switch_impl",
    "serve",
    "serve_dispatch",
    "switch",
    "switch_impl",
]


def serve(
    config_id: str = typer.Argument(..., help="Config id to start."),
    foreground: bool = typer.Option(
        False, "--foreground", help="Run attached to this terminal."
    ),
    systemd: bool = typer.Option(
        False, "--systemd", help="Bind loco.service to this config."
    ),
    foreground_from_supervisor: bool = typer.Option(
        False, "--foreground-from-supervisor", hidden=True
    ),
) -> None:
    """Start a server for <config_id>."""
    try:
        serve_dispatch(
            config_id,
            foreground=foreground,
            systemd=systemd,
            foreground_from_supervisor=foreground_from_supervisor,
            on_message=serve_status_message,
        )
    except ServeError as exc:
        raise_serve_exit(exc)


def switch(
    config_id: str = typer.Argument(..., help="New config id."),
) -> None:
    """Stop the currently-running service and start <config_id> in the same mode."""
    try:
        switch_impl(config_id, on_message=serve_status_message)
    except ServeError as exc:
        raise_serve_exit(exc)
