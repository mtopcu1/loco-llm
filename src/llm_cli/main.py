"""LocalLLM CLI entrypoint."""
from typing import Optional

import typer

from llm_cli import __version__
from llm_cli.commands import init as init_cmd
from llm_cli.commands import specs as specs_cmd
from llm_cli.commands.doctor import doctor_app

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


app.command("init", help="Read paths.yaml, create data-root dirs, write .llm-env.")(init_cmd.init)
app.command("specs", help="Regenerate the auto block in specs.md.")(specs_cmd.specs_command)
app.add_typer(doctor_app, name="doctor")
