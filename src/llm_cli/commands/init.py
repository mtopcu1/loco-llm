"""`llm init` — read paths.yaml, create data root layout, write .llm-env."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.paths import load_paths

console = Console()


def _repo_root() -> Path:
    """Locate the repo root.

    Tests inject LLM_REPO_ROOT; otherwise we fall back to the CWD. Later
    milestones may add a more sophisticated discovery (walk up looking for
    paths.yaml).
    """
    explicit = os.environ.get("LLM_REPO_ROOT")
    if explicit:
        return Path(explicit)
    return Path.cwd()


def init() -> None:
    """Read paths.yaml, create data-root subdirectories, write .llm-env."""
    repo = _repo_root()
    paths_yaml = repo / "paths.yaml"
    if not paths_yaml.is_file():
        console.print(f"[red]error:[/red] paths.yaml not found at {paths_yaml}")
        raise typer.Exit(code=1)

    paths = load_paths(paths_yaml)

    for target in (paths.data_root, paths.runtimes, paths.models, paths.cache):
        target.mkdir(parents=True, exist_ok=True)

    env_file = repo / ".llm-env"
    lines = [f"{k}={v}" for k, v in paths.to_env_dict().items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    console.print(f"[green]initialized[/green] data root at {paths.data_root}")
    console.print(f"[green]wrote[/green] {env_file}")
