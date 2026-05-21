"""`loco advisor` — surface VRAM-aware recommendations."""
from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.lifecycle import append_history, state_root
from llm_cli.core.model_registry import get_entry as _get_model
from llm_cli.core.recommendations import Recommendation, recommend
from llm_cli.core.repo import scaffold_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.specs import detect_all

console = Console()


def _offer_create_config(runtime_id: str, model_id: str) -> bool:
    from llm_cli.core import wizards as wiz

    return wiz.confirm(
        f"Create a config for {runtime_id} + {model_id} now?",
        default=False,
    )


def _render_text(
    runtime_id: str,
    model_id: str,
    specs,
    recs: dict[str, Recommendation],
) -> None:
    console.print(
        f"[bold]Recommendations for {runtime_id} + {model_id} on this machine[/bold]"
    )
    if specs.gpus:
        g = specs.gpus[0]
        console.print(f"GPU: {g.name} ({g.vram_gb} GB)\n")
    if not recs:
        console.print("No recommendations available for this combination.")
        return
    for key, rec in recs.items():
        console.print(
            f"  [bold cyan]{key}[/bold cyan]  suggested [bold green]{rec.value}[/bold green]"
        )
        console.print(f"                [dim italic]{rec.reason}[/dim italic]\n")
    console.print(
        "Notes:\n"
        "  • Estimates based on llama.cpp's typical KV cost; actual VRAM use "
        "varies\n"
        "    with quant and prompt length.\n"
        "  • Run  loco config setup  to scaffold a config using these values.\n"
    )


def _render_json(
    runtime_id: str,
    model_id: str,
    specs,
    recs: dict[str, Recommendation],
) -> None:
    payload = {
        "runtime": runtime_id,
        "model": model_id,
        "machine": {
            "gpus": [{"name": g.name, "vram_gb": g.vram_gb} for g in specs.gpus],
        },
        "recommendations": {
            k: {"value": r.value, "reason": r.reason} for k, r in recs.items()
        },
    }
    typer.echo(json.dumps(payload, indent=2))


def do_advisor(
    *,
    runtime_id: str,
    model_id: str,
    as_json: bool = False,
    history_from: str = "flags",
) -> int:
    """Render advice for (runtime_id, model_id). Returns exit code."""
    settings = resolve(load_settings())

    rt_manifest = registry.get_runtime_manifest_merged(runtime_id)
    if rt_manifest is None:
        console.print(f"[red]error:[/red] no runtime named {runtime_id!r}")
        return 1

    model = _get_model(settings.models_dir, model_id)
    if model is None:
        console.print(f"[red]error:[/red] no model named {model_id!r} in registry")
        return 1

    specs = detect_all(
        repo_root=scaffold_root().as_posix(),
        data_root=settings.data_root.as_posix(),
    )
    recs: dict[str, Recommendation] = {}
    for spec in rt_manifest.serve_schema:
        r = recommend(runtime_id, spec.key, model=model, specs=specs)
        if r is not None:
            recs[spec.key] = r

    if as_json:
        _render_json(runtime_id, model_id, specs, recs)
    else:
        _render_text(runtime_id, model_id, specs, recs)

    if not recs:
        return 1

    append_history(
        state_root(settings),
        {
            "action": "advisor",
            "runtime": runtime_id,
            "model": model_id,
            "from": history_from,
        },
    )
    return 0


def _interactive_pick() -> tuple[str | None, str | None]:
    from llm_cli.core import wizards as wiz

    settings = resolve(load_settings())

    runtimes = registry.load_runtime_manifests_merged()
    if not runtimes:
        console.print("[red]error:[/red] no runtimes found in runtimes/")
        return (None, None)

    runtime_id = wiz.select("Pick a runtime", [rt.id for rt in runtimes])
    rt_manifest = next(rt for rt in runtimes if rt.id == runtime_id)
    if not rt_manifest.accepts_formats:
        console.print(
            f"[red]error:[/red] runtime {runtime_id!r} needs no model; "
            "interactive advisor requires a runtime that consumes a model"
        )
        return (None, None)

    from llm_cli.core.model_registry import load_registry

    models = [
        m
        for m in load_registry(settings.models_dir).values()
        if m.format in rt_manifest.accepts_formats
    ]
    if not models:
        console.print(
            f"[red]error:[/red] no models in registry match accepts_formats "
            f"{list(rt_manifest.accepts_formats)}. Try `loco model pull <hf-url>`."
        )
        return (None, None)
    model_id = wiz.select("Pick a model", [m.id for m in models])
    return (runtime_id, model_id)


def advisor(
    config_id: Optional[str] = typer.Argument(
        None,
        help="Existing config id to advise against.",
    ),
    runtime: Optional[str] = typer.Option(
        None, "--runtime", help="Runtime id (requires --model)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Model id (requires --runtime)."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
) -> None:
    """Show VRAM-aware suggestions for a (runtime, model) pair."""
    if config_id is not None and (runtime is not None or model is not None):
        console.print(
            "[red]error:[/red] use either a config id or --runtime/--model, not both"
        )
        raise typer.Exit(code=1)

    if (runtime is None) != (model is None):
        console.print(
            "[red]error:[/red] both --runtime and --model are required when "
            "not using interactive or config-id mode"
        )
        raise typer.Exit(code=1)

    history_from = "flags"
    if config_id is not None:
        cfg = registry.get_config_merged(config_id)
        if cfg is None:
            console.print(f"[red]error:[/red] no config named {config_id!r}")
            raise typer.Exit(code=1)
        runtime = str(cfg.data.get("runtime", ""))
        model_val = cfg.data.get("model")
        if not runtime or not isinstance(model_val, str):
            console.print(
                f"[red]error:[/red] config {config_id!r} has no runtime/model "
                "to advise on"
            )
            raise typer.Exit(code=1)
        model = model_val
        history_from = "config"
    elif runtime is None:
        runtime, model = _interactive_pick()
        if runtime is None or model is None:
            raise typer.Exit(code=1)
        history_from = "interactive"

    assert runtime is not None and model is not None
    rc = do_advisor(
        runtime_id=runtime,
        model_id=model,
        as_json=as_json,
        history_from=history_from,
    )
    if rc != 0:
        raise typer.Exit(code=rc)

    if not as_json and rc == 0:
        if _offer_create_config(runtime, model):
            from llm_cli.commands.config_cmd import do_config_setup

            do_config_setup(runtime_id=runtime, model_id=model)
