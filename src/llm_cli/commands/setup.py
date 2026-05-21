"""`loco setup` — first-run onboarding wizard (runtime → model → config)."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.commands.setup_chain import run_setup_chain
from llm_cli.core.settings import (
    ensure_data_dirs,
    load_settings,
    resolve,
    settings_path,
)

console = Console()

_INSTALL_HINT = """\
[red]error:[/red] data home not initialized — run the installer first:
  curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
Paths can be changed later with: [bold]loco settings edit data_root[/bold]"""


def setup() -> None:
    """First-run wizard: runtime, model, launch config, optional serve."""
    cfg_path = settings_path()
    if not cfg_path.is_file():
        console.print(_INSTALL_HINT)
        raise typer.Exit(1)

    stored = load_settings()
    if not str(stored.get("data_root", "")).strip():
        console.print(_INSTALL_HINT)
        raise typer.Exit(1)

    ensure_data_dirs(resolve(stored))
    raise typer.Exit(run_setup_chain())
