"""`llm setup` — first-run interactive configurator."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.scaffold import scaffold_root
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
    raw = os.environ.get(
        "LLM_DEFAULT_DATA_ROOT", KEY_REGISTRY["data_root"]["default"]
    )
    return _path_display(Path(raw))


def _detect_dev_repo_root() -> Path | None:
    """When cwd is a git checkout, offer repo_root for editable dev installs."""
    cwd = Path.cwd().resolve()
    if (cwd / ".git").is_dir():
        return cwd
    return None


def _maybe_bootstrap_scaffold_message() -> None:
    root = scaffold_root()
    if not root.is_dir():
        console.print(
            "[yellow]note:[/yellow] scaffold assets are not installed yet; "
            "run `llm update --scaffold-only` after setup."
        )
        return
    try:
        has_assets = any(root.iterdir())
    except OSError:
        has_assets = False
    if not has_assets:
        console.print(
            "[yellow]note:[/yellow] scaffold directory is empty; "
            "run `llm update --scaffold-only` to fetch official assets."
        )


def setup(
    default: bool = typer.Option(
        False, "--default", help="Non-interactive: use defaults for every key."
    ),
) -> None:
    """Configure machine-local settings (~/.config/llm/config.yaml)."""
    cfg_path = settings_path()
    if cfg_path.is_file():
        if default:
            console.print(
                f"[dim]note:[/dim] overwriting existing settings at {cfg_path}"
            )
        elif not typer.confirm(
            f"Settings file already exists at {cfg_path}. Overwrite?",
            default=False,
        ):
            console.print("[yellow]setup cancelled[/yellow]")
            raise typer.Exit(0)

    stored: dict[str, str] = {}

    dev_repo = _detect_dev_repo_root()
    if dev_repo is not None:
        stored["repo_root"] = str(dev_repo)

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
            if not overrides:
                console.print(
                    "[dim]note:[/dim] no directory overrides set; "
                    "using default layout under data_root."
                )
        if dev_repo is not None and typer.confirm(
            f"Use this checkout as repo_root for development ({dev_repo})?",
            default=True,
        ):
            stored["repo_root"] = str(dev_repo)
        elif "repo_root" in stored:
            del stored["repo_root"]

    path = save_settings(stored)
    resolved = resolve(load_settings())
    ensure_data_dirs(resolved)
    _maybe_bootstrap_scaffold_message()
    console.print(f"[green]wrote[/green] {path}")
    console.print(f"[green]data_root[/green]: {_path_display(resolved.data_root)}")
    console.print(
        f"[green]runtimes_dir[/green]: {_path_display(resolved.runtimes_dir)}"
    )
    console.print(f"[green]models_dir[/green]: {_path_display(resolved.models_dir)}")
    console.print(f"[green]cache_dir[/green]: {_path_display(resolved.cache_dir)}")
    if resolved.repo_root is not None:
        console.print(f"[green]repo_root[/green]: {_path_display(resolved.repo_root)}")
    else:
        console.print("[dim]repo_root[/dim]: (not set — using managed scaffold)")

    if default:
        console.print()
        console.print("[bold]Recommended next steps:[/bold]")
        console.print("  1. llm doctor                  # verify cross-cutting prereqs")
        console.print("  2. llm runtime setup           # install or register a runtime")
        console.print("  3. llm model pull <hf-url>     # download a model")
        console.print("  4. llm config setup            # scaffold a config")
        console.print("  5. llm serve <config-id>       # start a server")
        return

    console.print()
    from llm_cli.core.chain import run_setup_chain

    rc = run_setup_chain()
    if rc != 0:
        raise typer.Exit(code=rc)


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
