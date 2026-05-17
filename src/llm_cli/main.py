"""LocalLLM CLI entrypoint."""
from typing import Optional

import typer

from llm_cli import __version__
from llm_cli.commands import artifacts, config_cmd, list_cmd
from llm_cli.commands import setup as setup_cmd
from llm_cli.commands import specs as specs_cmd
from llm_cli.commands import lifecycle_cmds
from llm_cli.commands.model_cmd import model_app
from llm_cli.commands.runtime_cmd import runtime_app
from llm_cli.commands import serve as serve_cmd
from llm_cli.commands.doctor import doctor_app
from llm_cli.commands.settings_cmd import settings_app

app = typer.Typer(
    name="llm",
    help="LocalLLM — control plane for local LLM runtimes.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llm {__version__}")
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
    """LocalLLM CLI — manage runtimes, models, configs, and benchmarks."""


app.command("setup", help="Configure machine-local settings.")(setup_cmd.setup)
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
app.command("build", help="Run runtimes/<id>/build.sh in WSL with LLM_* env.")(
    artifacts.build_runtime
)
app.command("pull", help="Run models/<id>/pull.sh in WSL with LLM_* env.")(
    artifacts.pull_model
)

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
