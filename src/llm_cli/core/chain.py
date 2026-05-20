"""Orchestration for `loco setup` onboarding chain."""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from llm_cli.core.lifecycle import append_history

console = Console()


def _confirm(prompt: str, *, default: bool = True) -> bool:
    from llm_cli.core import wizards as wiz

    return wiz.confirm(prompt, default=default)


def _prompt_text(prompt: str, *, default: str = "") -> str:
    from llm_cli.core import wizards as wiz

    return wiz.text(prompt, default=default)


def _do_runtime_setup() -> str | None:
    from llm_cli.commands.runtime_cmd import interactive_runtime_setup

    return interactive_runtime_setup()


def _duplicate_model_menu(existing_id: str) -> str:
    """Return keep | force | rename | skip."""
    from llm_cli.core import wizards as wiz

    choice = wiz.select(
        f"Model `{existing_id}` is already registered for this URL.",
        [
            "Keep existing — skip download (use registered model)",
            "Re-download weights and overwrite registry entry",
            "Register under a different local model id",
            "Skip — continue setup without this model",
        ],
    )
    if choice.startswith("Keep existing"):
        return "keep"
    if choice.startswith("Re-download"):
        return "force"
    if choice.startswith("Register under"):
        return "rename"
    return "skip"


def _pull_with_new_model_id(url: str) -> str | None:
    """Prompt until unique id or user-visible failure; returns None on aborted pull."""
    from llm_cli.commands.model_cmd import (
        DuplicateModelRegistrationError,
        PullModelError,
    )
    from llm_cli.core import wizards as wiz
    from llm_cli.core.model_registry import get_entry
    from llm_cli.core.settings import load_settings, resolve as resolve_settings

    models_dir = resolve_settings(load_settings()).models_dir

    def validate(v: str) -> str | None:
        t = v.strip()
        if not t:
            return "id is required"
        if len(t) > 128:
            return "id too long"
        for ch in t:
            if not (ch.isalnum() or ch in "-_."):
                return "use letters, digits, dashes, underscores, dots only"
        return None

    while True:
        new_id = wiz.text(
            "Local model id (must not already exist)",
            validate=validate,
        ).strip()
        if get_entry(models_dir, new_id) is not None:
            console.print(
                f"[red]error:[/red] {new_id!r} is already registered — choose another id"
            )
            continue
        try:
            return _do_model_pull(url, id_override=new_id)
        except DuplicateModelRegistrationError:
            console.print(
                "[red]error:[/red] that id still conflicts — try a different id"
            )
            continue
        except PullModelError as exc:
            console.print(f"[red]error:[/red] {exc}")
            return None


def _interactive_model_pull_for_setup(url: str) -> str | None:
    """Pull HF URL or resolve duplicate registration interactively."""
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

    try:
        return _do_model_pull(url)
    except DuplicateModelRegistrationError as dup:
        decision = _duplicate_model_menu(dup.model_id)
        if decision == "keep":
            return dup.model_id
        if decision == "skip":
            console.print("[yellow]skipped[/yellow] model pull")
            return None
        if decision == "force":
            return _do_model_pull(url, force=True)
        return _pull_with_new_model_id(url)


def _do_model_pull(url: str, **kwargs: Any) -> str:
    from llm_cli.commands.model_cmd import do_model_pull

    return do_model_pull(url, **kwargs)


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


def _do_dashboard_install() -> None:
    from llm_cli.commands.dashboard_cmd import install as dashboard_install

    dashboard_install()


def run_setup_chain() -> int:
    """Interactive post-settings chain (runtime → model URL → config → serve)."""
    from llm_cli.commands.model_cmd import PullModelError
    from llm_cli.core.lifecycle import append_history, state_root
    from llm_cli.core.settings import load_settings, resolve

    settings = resolve(load_settings())
    state_base = state_root(settings)
    steps: list[str] = []
    runtime_id: str | None = None
    model_id: str | None = None
    config_id: str | None = None

    if _confirm("Install / register a runtime now?", default=True):
        try:
            picked = _do_runtime_setup()
        except typer.Exit as exc:
            append_history(
                state_base,
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
            model_id = _interactive_model_pull_for_setup(url_raw)
        except PullModelError as exc:
            console.print(f"[red]error:[/red] {exc}")
            append_history(
                state_base,
                {"action": "setup-chain", "steps": steps, "outcome": "model-pull-failed"},
            )
            return 1
        if model_id:
            console.print(f"[green]model[/green] {model_id}")
            steps.append("model-pull")

    config_default = model_id is not None
    if not config_default:
        console.print(
            "[dim]Tip:[/dim] pull a model first (`loco model pull <hf-url>`), "
            "then run `loco config setup`."
        )
    if _confirm("Create a launch config now?", default=config_default):
        cid = _do_config_setup(
            runtime_id=runtime_id,
            model_id=model_id,
            preset="default",
        )
        if cid is None:
            console.print("[red]error:[/red] config setup aborted")
            append_history(
                state_base,
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
                state_base,
                {"action": "setup-chain", "steps": steps, "outcome": "serve-failed"},
            )
            return code
        steps.append("serve")

    append_history(state_base, {"action": "setup-chain", "steps": steps, "outcome": "ok"})

    if config_id and "serve" in steps:
        console.print("\n[green]Tip:[/green] run `loco status` to inspect the server.")
    elif config_id:
        console.print(f"\n[dim]Next:[/dim] loco serve {config_id}")

    if _confirm("Install the web dashboard now?", default=False):
        try:
            _do_dashboard_install()
            steps.append("dashboard-install")
        except typer.Exit as exc:
            if int(exc.exit_code or 1) != 0:
                console.print(
                    "[yellow]Dashboard install failed; continuing setup. "
                    "Run `loco dashboard install` to retry.[/yellow]"
                )

    return 0
