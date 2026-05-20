"""`llm dashboard ...` command group."""
from __future__ import annotations

from typing import Annotated

import typer

from llm_cli.core import dashboard as dash
from llm_cli.core.versions import current_cli_version

app = typer.Typer(help="Manage the LocalLLM web dashboard.")
_LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}

_INSECURE_REFUSAL = """

═══════════════════════════════════════════════════════════════════════
  REFUSING TO START: --insecure exposes the dashboard on the network.
═══════════════════════════════════════════════════════════════════════

What --insecure means:
  • Anyone reachable on this interface can manage your LocalLLM install.
  • That includes pulling arbitrary models, starting runtimes, viewing
    your config files, and reading runtime stdout/stderr (which may
    contain prompts).
  • There is no authentication. There is no audit log.
  • This is unsafe on shared networks (coffee shops, conferences, dorms).
  • This is unsafe on cloud VMs without firewall rules.

If you actually need remote access, prefer:
  • SSH port-forward:    ssh -L 7878:127.0.0.1:7878 user@host
  • Tailscale + bind to the tailnet IP only
  • A reverse proxy with TLS and auth in front (out of scope for v1)

If you understand and accept the risk, re-run with --i-understand:
  llm dashboard serve --insecure --i-understand --allowed-host <host:port>

See: docs/DASHBOARD-SECURITY.md
"""


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
    insecure: Annotated[bool, typer.Option("--insecure")] = False,
    i_understand: Annotated[bool, typer.Option("--i-understand")] = False,
    allowed_host: Annotated[list[str], typer.Option("--allowed-host")] = [],
) -> None:
    """Start the dashboard server."""
    if insecure and not i_understand:
        typer.secho(_INSECURE_REFUSAL, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=78)

    if insecure and i_understand and not allowed_host:
        typer.secho(
            "Refusing to start: --insecure --i-understand requires at least one "
            "--allowed-host HOST:PORT (DNS rebinding defense). See docs/DASHBOARD-SECURITY.md.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=78)

    if not insecure and host not in _LOCALHOST_HOSTS:
        typer.secho(
            f"Refusing to bind to {host}. Non-localhost binding requires "
            "--insecure --i-understand --allowed-host HOST:PORT.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=78)

    if insecure and i_understand:
        typer.secho(_INSECURE_REFUSAL.rstrip(), fg=typer.colors.YELLOW, err=True)
        typer.echo("")

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

    allowed_hosts: set[str] = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if insecure:
        allowed_hosts.update(allowed_host)

    if foreground:
        typer.echo(
            f"Starting dashboard on http://{host}:{port}/ (foreground; Ctrl-C to stop)"
        )
        if not no_open:
            dash.open_browser(host, port)
        dash.run_server_foreground(
            host, port, allowed_hosts=allowed_hosts, insecure=insecure
        )
        return

    try:
        pid = dash.start_server_background(
            host, port, allowed_hosts=allowed_hosts, insecure=insecure
        )
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
    if dash.stop_server():
        typer.echo("Dashboard stopped.")
    else:
        typer.echo("No dashboard server is running.")


@app.command()
def uninstall(
    purge: Annotated[bool, typer.Option("--purge", help="Delete dashboard/dist and dashboard/node_modules.")] = False,
) -> None:
    """Remove the .installed marker (and optionally build artifacts)."""
    marker = dash.installed_marker_path()
    if marker.exists():
        marker.unlink()
    if purge:
        import shutil

        shutil.rmtree(dash.dist_dir(), ignore_errors=True)
        shutil.rmtree(dash.dashboard_root() / "node_modules", ignore_errors=True)
        typer.echo("Removed .installed, dist/, and node_modules/.")
    else:
        typer.echo("Removed .installed (use --purge to also delete dist/ and node_modules/).")
