"""Loco CLI entrypoint."""
from __future__ import annotations

import subprocess
from typing import Optional

import typer

from llm_cli import __version__
from llm_cli.core.scaffold import scaffold_root
from llm_cli.commands import config_cmd, list_cmd
from llm_cli.commands import setup as setup_cmd
from llm_cli.commands import specs as specs_cmd
from llm_cli.commands import lifecycle_cmds
from llm_cli.commands.model_cmd import model_app
from llm_cli.commands.runtime_cmd import runtime_app
from llm_cli.commands import serve as serve_cmd
from llm_cli.commands.advisor import advisor as advisor_cmd
from llm_cli.commands.doctor import doctor_app
from llm_cli.commands.settings_cmd import settings_app
from llm_cli.commands.update_cmd import update as update_cmd
from llm_cli.commands.dashboard_cmd import app as dashboard_app

app = typer.Typer(
    name="loco",
    help="Loco — control plane for local LLM runtimes.",
    no_args_is_help=True,
)


def _head_suffix() -> str:
    try:
        root = scaffold_root()
    except RuntimeError:
        return ""
    try:
        tag = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip()
        if tag:
            return ""
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    try:
        branch = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip()
        if branch and branch != "HEAD":
            return f" (branch: {branch})"
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip()
        return f" (detached: {sha})" if sha else ""
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"loco {__version__}{_head_suffix()}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Loco CLI — manage runtimes, models, configs, and benchmarks."""


app.command(
    "setup",
    help="First-run wizard: runtime, model, launch config, optional serve.",
)(setup_cmd.setup)
app.command("update", help="Upgrade CLI and scaffold assets.")(update_cmd)
app.command("specs", help="Regenerate the auto block in specs.md.")(specs_cmd.specs_command)
app.add_typer(doctor_app, name="doctor")
app.add_typer(settings_app, name="settings")
app.add_typer(runtime_app, name="runtime")
app.add_typer(model_app, name="model")
app.command(
    "list",
    help="List discovered runtimes, models, configs, and benchmarks.",
)(list_cmd.list_entities)
app.add_typer(config_cmd.config_app, name="config")
app.add_typer(dashboard_app, name="dashboard")

app.command(
    "advisor",
    help="VRAM-aware recommendations for a (runtime, model) pair.",
)(advisor_cmd)

# Lifecycle: serve, switch, stop, status, logs.
app.command("serve", help="Start a config in fg/bg/systemd mode.")(serve_cmd.serve)
app.command(
    "switch",
    help="Stop the current service and start a new config in the same mode.",
)(serve_cmd.switch)
app.command("stop", help="Stop the currently-running service.")(lifecycle_cmds.stop)
app.command("status", help="Show what's currently running.")(lifecycle_cmds.status)
app.command("logs", help="Tail logs of the currently-running service.")(
    lifecycle_cmds.logs
)
