"""`loco specs` — regenerate the auto block in specs.md."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.repo import scaffold_root
from llm_cli.core.settings import MissingSettingError, load_settings, resolve
from llm_cli.core.specs import (
    MarkersMissingError,
    detect_all,
    render_specs_block,
    update_specs_markdown,
)

console = Console()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gather_block(repo: Path) -> str:
    data_root = "not detected"
    try:
        data_root = resolve(load_settings()).data_root.as_posix()
    except (MissingSettingError, ValueError):
        pass
    specs = detect_all(repo_root=repo.resolve().as_posix(), data_root=data_root)
    return render_specs_block(specs, generated_at=_utcnow_iso())


def specs_command(
    check: bool = typer.Option(
        False, "--check", help="Compare detection against specs.md; exit nonzero on drift."
    ),
    print_only: bool = typer.Option(
        False, "--print", help="Print detection result without writing specs.md."
    ),
    force: bool = typer.Option(
        False, "--force", help="Recreate specs.md from scratch if markers are missing."
    ),
) -> None:
    """Regenerate the auto block in specs.md."""
    repo = scaffold_root()
    new_block = _gather_block(repo)

    if print_only:
        typer.echo(new_block)
        raise typer.Exit(code=0)

    specs_md = repo / "specs.md"

    if check:
        if not specs_md.is_file():
            console.print("[red]drift:[/red] specs.md does not exist")
            raise typer.Exit(code=2)
        current = specs_md.read_text(encoding="utf-8")
        try:
            updated = update_specs_markdown(current, new_block)
        except MarkersMissingError:
            console.print("[red]drift:[/red] specs.md is missing markers")
            raise typer.Exit(code=2)

        def _strip_timestamp(text: str) -> str:
            return "\n".join(
                line for line in text.splitlines() if not line.startswith("_Generated:")
            )

        if _strip_timestamp(current) == _strip_timestamp(updated):
            console.print("[green]ok:[/green] specs.md matches detected specs")
            raise typer.Exit(code=0)
        console.print("[yellow]drift:[/yellow] specs.md does not match detected specs")
        raise typer.Exit(code=1)

    existing = specs_md.read_text(encoding="utf-8") if specs_md.is_file() else ""
    try:
        new_text = update_specs_markdown(existing or "", new_block, force=force or not existing)
    except MarkersMissingError:
        console.print(
            "[red]error:[/red] specs.md is missing the llm:specs markers (use --force to recreate)"
        )
        raise typer.Exit(code=1)

    specs_md.write_text(new_text, encoding="utf-8")
    console.print(f"[green]wrote[/green] {specs_md}")
