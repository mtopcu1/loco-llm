"""`llm setup` — configure the data home (Hermes-style; paths seeded by install.sh)."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.scaffold import install_root, seed_configs_from_install
from llm_cli.core.settings import (
    KEY_REGISTRY,
    ensure_data_dirs,
    load_settings,
    resolve,
    save_settings,
    settings_path,
)

console = Console()


def _path_display(path: Path) -> str:
    return path.expanduser().resolve().as_posix()


def _default_data_root() -> str:
    for key in ("LOCO_HOME", "LOCO_LLM_DATA", "LLM_DEFAULT_DATA_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return _path_display(Path(raw))
    return KEY_REGISTRY["data_root"]["default"]


def _detect_dev_repo_root() -> Path | None:
    """When cwd is a git checkout, offer repo_root for editable dev installs."""
    cwd = Path.cwd().resolve()
    if (cwd / ".git").is_dir():
        return cwd
    return None


def setup(
    default: bool = typer.Option(
        False, "--default", help="Non-interactive: use defaults for every key."
    ),
) -> None:
    """Write {data_home}/config.yaml and ensure directory layout."""
    cfg_path = settings_path()
    if cfg_path.is_file():
        if default:
            console.print(
                f"[dim]note:[/dim] refreshing settings at {cfg_path}"
            )
        elif not typer.confirm(
            f"Settings file already exists at {cfg_path}. Overwrite?",
            default=False,
        ):
            console.print("[yellow]setup cancelled[/yellow]")
            raise typer.Exit(0)

    stored: dict[str, str] = {}
    dev_repo = _detect_dev_repo_root()

    if default:
        stored["data_root"] = _default_data_root()
    else:
        stored["data_root"] = typer.prompt(
            KEY_REGISTRY["data_root"]["prompt"],
            default=_default_data_root(),
        )
        granular = typer.confirm(
            "Use default subdirectory layout under data_root?",
            default=True,
        )
        if not granular:
            overrides = _prompt_dir_overrides(stored["data_root"])
            stored.update(overrides)
        if dev_repo is not None and typer.confirm(
            f"Use this checkout as repo_root for development ({dev_repo})?",
            default=True,
        ):
            stored["repo_root"] = str(dev_repo)

    path = save_settings(stored)
    resolved = resolve(load_settings())
    ensure_data_dirs(resolved)
    try:
        seeded = seed_configs_from_install()
        if seeded:
            console.print(
                f"[dim]seeded {len(seeded)} config(s) into "
                f"{resolved.data_root / 'configs'}[/dim]"
            )
    except RuntimeError:
        console.print(
            "[yellow]note:[/yellow] install root not found; "
            "run install.sh or set LOCO_INSTALL before seeding example configs."
        )

    console.print(f"[green]wrote[/green] {path}")
    console.print(f"[green]data_root[/green]: {_path_display(resolved.data_root)}")
    try:
        console.print(f"[green]install[/green]: {_path_display(install_root())}")
    except RuntimeError:
        console.print("[dim]install[/dim]: (not resolved — set LOCO_INSTALL)")
    console.print(
        f"[green]configs[/green]: {_path_display(resolved.data_root / 'configs')}"
    )
    if resolved.repo_root is not None:
        console.print(f"[green]repo_root[/green]: {_path_display(resolved.repo_root)}")
    else:
        console.print("[dim]repo_root[/dim]: (not set — managed install)")

    console.print()
    console.print("[bold]Recommended next steps:[/bold]")
    console.print("  1. loco doctor")
    console.print("  2. loco runtime setup")
    console.print("  3. loco model pull <hf-url>")
    console.print("  4. loco config setup")
    console.print("  5. loco serve <config-id>")


def _prompt_dir_overrides(data_root: str) -> dict[str, str]:
    """Prompt for each dir key; empty answer omits the key so it stays derived."""
    overrides: dict[str, str] = {}
    data_root_path = Path(data_root).expanduser()
    for key in ("runtimes_dir", "models_dir", "cache_dir"):
        meta = KEY_REGISTRY[key]
        derived = data_root_path / meta["derived_suffix"]
        answer = typer.prompt(meta["prompt"], default="", show_default=False)
        answer = answer.strip()
        if answer and answer != str(derived):
            overrides[key] = answer
    return overrides
