"""`llm dashboard ...` command group."""
from __future__ import annotations

from typing import Annotated

import typer

from llm_cli.core import dashboard as dash
from llm_cli.core.versions import current_cli_version

app = typer.Typer(help="Manage the LocalLLM web dashboard.")
_LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Bare `llm dashboard` → alias for `llm dashboard serve`."""
    if ctx.invoked_subcommand is None:
        serve()


@app.command()
def install(
    reset: Annotated[bool, typer.Option("--reset", help="Wipe node_modules first.")] = False,
    skip_frontend: Annotated[bool, typer.Option("--skip-frontend")] = False,
    skip_python: Annotated[bool, typer.Option("--skip-python")] = False,
) -> None:
    """Install Python deps + Node deps + build the frontend."""
    try:
        record = dash.run_install(
            cli_version=current_cli_version(),
            skip_python=skip_python,
            skip_frontend=skip_frontend,
            reset=reset,
        )
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=78) from exc
    typer.secho(
        f"Dashboard installed (CLI {record.cli_version}, node {record.node_version}, "
        f"npm {record.npm_version}).",
        fg=typer.colors.GREEN,
    )


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port")] = 7878,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    foreground: Annotated[bool, typer.Option("--foreground")] = False,
    no_open: Annotated[bool, typer.Option("--no-open")] = False,
) -> None:
    """Start the dashboard server."""
    if host not in _LOCALHOST_HOSTS:
        typer.secho(
            f"Refusing to bind to {host}. Non-localhost binding requires --insecure "
            "(planned for a later security hardening release).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=78)

    verdict, reason = dash.verify_installed(current_cli_version())
    if verdict != "ok":
        hint = " --reset" if verdict in {"version_mismatch", "hash_mismatch"} else ""
        typer.secho(
            f"Dashboard is not ready ({verdict}): {reason}. "
            f"Run `llm dashboard install{hint}`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=78)

    if foreground:
        typer.echo(
            f"Starting dashboard on http://{host}:{port}/ (foreground; Ctrl-C to stop)"
        )
        if not no_open:
            dash.open_browser(host, port)
        dash.run_server_foreground(host, port)
        return

    try:
        pid = dash.start_server_background(host, port)
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Dashboard started on http://{host}:{port}/ (pid {pid})", fg=typer.colors.GREEN)
    if not no_open:
        dash.open_browser(host, port)


@app.command()
def status() -> None:
    """Print dashboard install + server status."""
    try:
        record = dash.load_installed_record()
    except RuntimeError:
        typer.echo("Dashboard not installed. Run `llm dashboard install`.")
        raise typer.Exit(code=0)
    if record is None:
        typer.echo("Dashboard not installed. Run `llm dashboard install`.")
        raise typer.Exit(code=0)
    typer.echo(f"Installed for CLI {record.cli_version} at {record.installed_at}")
    pid = dash.read_server_pid()
    if pid is None:
        typer.echo("Server: not running")
        return
    alive = dash.is_server_alive(pid)
    typer.echo(f"Server: {'running' if alive else 'stale pid file'} (pid={pid})")


@app.command()
def stop() -> None:
    """Stop the dashboard server."""
    typer.secho("`llm dashboard stop` not yet implemented (Plan 1, Task 15).", fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@app.command()
def uninstall(
    purge: Annotated[bool, typer.Option("--purge", help="Delete dashboard/dist and dashboard/node_modules.")] = False,
) -> None:
    """Remove the .installed marker (and optionally build artifacts)."""
    typer.secho("`llm dashboard uninstall` not yet implemented (Plan 1, Task 15).", fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)
