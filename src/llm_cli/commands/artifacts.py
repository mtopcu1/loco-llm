"""`llm build` and `llm pull` — run WSL bash scripts for runtimes and models."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.wsl import run_repo_bash

console = Console()


def build_runtime(runtime_id: str = typer.Argument(..., help="Runtime id.")) -> None:
    """Run `runtimes/<id>/build.sh` inside WSL with LLM_* env injected."""
    repo = repo_root()
    rec = registry.get_runtime(repo, runtime_id)
    if rec is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    code = run_repo_bash(settings, f"runtimes/{runtime_id}/build.sh")
    if code != 0:
        console.print(f"[red]build failed[/red] with exit code {code}")
        raise typer.Exit(code=code)


def pull_model(model_id: str = typer.Argument(..., help="Model id.")) -> None:
    """Run `models/<id>/pull.sh` inside WSL with LLM_* env injected."""
    repo = repo_root()
    rec = registry.get_model(repo, model_id)
    if rec is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    code = run_repo_bash(settings, f"models/{model_id}/pull.sh")
    if code != 0:
        console.print(f"[red]pull failed[/red] with exit code {code}")
        raise typer.Exit(code=code)
