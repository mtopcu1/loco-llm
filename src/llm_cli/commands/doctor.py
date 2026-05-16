"""`llm doctor` — verify external requirements; `llm doctor render-requirements` regenerates the markdown."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.doctor import (
    CheckStatus,
    check_all,
    load_requirements,
    render_requirements_md,
)

console = Console()
doctor_app = typer.Typer(
    name="doctor",
    help="Verify external requirements (CUDA driver, Python, hf CLI, ...).",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _repo_root() -> Path:
    explicit = os.environ.get("LLM_REPO_ROOT")
    return Path(explicit) if explicit else Path.cwd()


def _requirements_yaml(repo: Path) -> Path:
    path = repo / "requirements.yaml"
    if not path.is_file():
        console.print(f"[red]error:[/red] requirements.yaml not found at {path}")
        raise typer.Exit(code=1)
    return path


_STATUS_STYLES = {
    CheckStatus.OK: "green",
    CheckStatus.OUTDATED: "yellow",
    CheckStatus.MISSING: "red",
    CheckStatus.UNKNOWN: "magenta",
    CheckStatus.ERROR: "red",
}


@doctor_app.callback()
def doctor(ctx: typer.Context) -> None:
    """Run all requirement checks and print a status table."""
    if ctx.invoked_subcommand is not None:
        return

    repo = _repo_root()
    reqs = load_requirements(_requirements_yaml(repo))
    results = check_all(reqs)

    table = Table(title="External Requirements")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Detected")
    table.add_column("Min")
    table.add_column("Hint", overflow="fold")

    bad = 0
    for r in results:
        style = _STATUS_STYLES.get(r.status, "white")
        if r.status not in (CheckStatus.OK,):
            bad += 1
        table.add_row(
            r.requirement.id,
            r.requirement.name,
            f"[{style}]{r.status.value}[/{style}]",
            r.detected_version or "-",
            r.requirement.min_version or "-",
            r.requirement.install_hint if r.status != CheckStatus.OK else "",
        )

    console.print(table)
    if bad:
        console.print(f"[red]{bad} requirement(s) need attention[/red]")
        raise typer.Exit(code=1)
    console.print("[green]all requirements satisfied[/green]")


@doctor_app.command(
    "render-requirements", help="Regenerate requirements.md from requirements.yaml."
)
def render_requirements() -> None:
    repo = _repo_root()
    reqs = load_requirements(_requirements_yaml(repo))
    md = render_requirements_md(reqs)
    out = repo / "requirements.md"
    out.write_text(md, encoding="utf-8")
    console.print(f"[green]wrote[/green] {out}")
