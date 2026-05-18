"""Orchestration for extended `llm setup` after settings are written."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.core.lifecycle import append_history

console = Console()


def _confirm(prompt: str, *, default: bool = True) -> bool:
    from llm_cli.core import wizards as wiz

    return wiz.confirm(prompt, default=default)


def _prompt_text(prompt: str, *, default: str = "") -> str:
    from llm_cli.core import wizards as wiz

    return wiz.text(prompt, default=default or None)


def _do_runtime_setup() -> str | None:
    from llm_cli.commands.runtime_cmd import interactive_runtime_setup

    return interactive_runtime_setup()


def _do_model_pull(url: str) -> str:
    from llm_cli.commands.model_cmd import do_model_pull

    return do_model_pull(url)


def _do_config_setup(
    *,
    runtime_id: str | None,
    model_id: str | None,
    preset: str = "default",
) -> str | None:
    from llm_cli.commands.config_cmd import do_config_setup

    return do_config_setup(
        runtime_id=runtime_id, model_id=model_id, preset=preset
    )


def _do_serve(config_id: str) -> int:
    from llm_cli.commands.serve import serve_dispatch

    try:
        serve_dispatch(config_id)
    except typer.Exit as exc:
        return int(exc.exit_code or 1)
    return 0


def run_setup_chain() -> int:
    """Interactive post-settings chain (runtime → model URL → config → serve)."""
    from llm_cli.commands.model_cmd import PullModelError
    from llm_cli.core.repo import repo_root as _repo_root

    repo = _repo_root()
    steps: list[str] = []
    runtime_id: str | None = None
    model_id: str | None = None
    config_id: str | None = None

    if _confirm("Install / register a runtime now?", default=True):
        try:
            picked = _do_runtime_setup()
        except typer.Exit as exc:
            append_history(
                repo,
                {
                    "action": "setup-chain",
                    "steps": steps,
                    "outcome": "runtime-setup-failed",
                },
            )
            return int(exc.exit_code or 1)
        if picked:
            runtime_id = picked
            steps.append("runtime-setup")
        else:
            console.print("[yellow]skipped[/yellow] runtime setup")

    url_raw = _prompt_text(
        "Hugging Face model URL (empty to skip)",
        default="",
    ).strip()
    if url_raw:
        try:
            model_id = _do_model_pull(url_raw)
        except PullModelError as exc:
            console.print(f"[red]error:[/red] {exc}")
            append_history(
                repo,
                {"action": "setup-chain", "steps": steps, "outcome": "model-pull-failed"},
            )
            return 1
        console.print(f"[green]model[/green] {model_id}")
        steps.append("model-pull")

    if _confirm("Create a launch config now?", default=True):
        cid = _do_config_setup(
            runtime_id=runtime_id,
            model_id=model_id,
            preset="default",
        )
        if cid is None:
            console.print("[red]error:[/red] config setup aborted")
            append_history(
                repo,
                {"action": "setup-chain", "steps": steps, "outcome": "aborted"},
            )
            return 1
        config_id = cid
        steps.append("config-create")

    if config_id and _confirm(
        f"Start serving `{config_id}` in the background?",
        default=True,
    ):
        code = _do_serve(config_id)
        if code != 0:
            append_history(
                repo,
                {"action": "setup-chain", "steps": steps, "outcome": "serve-failed"},
            )
            return code
        steps.append("serve")

    append_history(repo, {"action": "setup-chain", "steps": steps, "outcome": "ok"})

    if config_id and "serve" in steps:
        console.print("\n[green]Tip:[/green] run `llm status` to inspect the server.")
    elif config_id:
        console.print(f"\n[dim]Next:[/dim] llm serve {config_id}")

    return 0
