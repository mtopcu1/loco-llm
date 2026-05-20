"""`llm config` — show, validate, new, setup."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import typer
import yaml
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core.lifecycle import append_history, state_root
from llm_cli.core.model_bindings import (
    apply_model_bindings,
    bound_keys_to_skip,
)
from llm_cli.core.model_registry import get_entry, load_registry
from llm_cli.core.param_grid_models import MetaField
from llm_cli.core.params import validate_params
from llm_cli.core.recommendations import recommend
from llm_cli.core.repo import scaffold_root
from llm_cli.core.scaffold import configs_dir
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.specs import detect_all

console = Console()

config_app = typer.Typer(help="Inspect and validate configs/*.yaml.")


def _atomic_write_yaml(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".cfg-", suffix=".yaml", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _parse_param(token: str) -> tuple[str, str]:
    if "=" not in token:
        raise typer.BadParameter(f"--param must be key=value (got {token!r})")
    key, value = token.split("=", 1)
    key = key.strip()
    if not key:
        raise typer.BadParameter("--param key cannot be empty")
    return key, value.strip()


def do_config_new(
    *,
    runtime_id: str,
    model_id: Optional[str],
    preset: str = "default",
    port: int = 8080,
    host: str = "127.0.0.1",
    params: dict[str, str] | None = None,
    force: bool = False,
    via: str = "new",
    config_id: Optional[str] = None,
) -> str:
    """Write user/configs/<id>.yaml and return the config id."""
    settings = resolve(load_settings())
    rt = registry.get_runtime_manifest_merged(runtime_id)
    if rt is None:
        raise typer.BadParameter(f"no runtime named {runtime_id!r}")

    if rt.accepts_formats and not model_id:
        raise typer.BadParameter(
            f"runtime {runtime_id!r} declares accepts_formats="
            f"{list(rt.accepts_formats)}; pass --model"
        )
    if not rt.accepts_formats and model_id:
        raise typer.BadParameter(
            f"runtime {runtime_id!r} has empty accepts_formats; omit --model"
        )

    merged = apply_model_bindings(
        rt.serve_schema, dict(params or {}), model_id=model_id
    )
    coerced, errors = validate_params(rt.serve_schema, merged)
    if errors:
        for err in errors:
            console.print(f"[red]error:[/red] {err}")
        raise typer.Exit(code=1)

    derived = (
        f"{runtime_id}__{model_id}__{preset}"
        if model_id
        else f"{runtime_id}__{preset}"
    )
    cid = (config_id.strip() if config_id else derived)
    cfg_root = configs_dir(settings)
    out_path = cfg_root / f"{cid}.yaml"
    if out_path.exists() and not force:
        console.print(
            f"[red]error:[/red] {out_path} exists; pass --force to overwrite"
        )
        raise typer.Exit(code=1)

    doc: dict[str, Any] = {"id": cid, "runtime": runtime_id}
    if model_id:
        doc["model"] = model_id
    doc["serve"] = {
        "host": host,
        "port": port,
        "params": dict(coerced),
    }
    doc["readiness"] = {"timeout_seconds": 600}

    _atomic_write_yaml(out_path, doc)
    append_history(state_root(settings), {"action": "config-create", "id": cid, "via": via})
    typer.echo(cid)
    return cid


def do_config_setup(
    *,
    runtime_id: str | None,
    model_id: str | None,
    preset: str = "default",
) -> str | None:
    """Interactive config authoring; returns config id or None on abort."""
    from llm_cli.core import wizards as wiz

    settings = resolve(load_settings())
    specs = detect_all(
        repo_root=scaffold_root().as_posix(),
        data_root=settings.data_root.as_posix(),
    )

    manifests = registry.load_runtime_manifests_merged()
    if not manifests:
        console.print("[red]error:[/red] no runtimes found under runtimes/")
        return None

    if runtime_id is None:
        rid = wiz.select("Pick a runtime", [m.id for m in manifests])
    else:
        rid = runtime_id

    mf = registry.get_runtime_manifest_merged(rid)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {rid!r}")
        return None

    mid: str | None = model_id
    if mf.accepts_formats:
        entries = [
            m
            for m in load_registry(settings.models_dir).values()
            if m.format in mf.accepts_formats
        ]
        if not entries:
            console.print(
                "[red]error:[/red] no compatible models in registry; "
                "`llm model pull <hf-url>` first, then `llm config setup`."
            )
            return None
        if mid is None:
            mid = wiz.select("Pick a model", sorted(e.id for e in entries))
        elif get_entry(settings.models_dir, mid) is None:
            console.print(f"[red]error:[/red] unknown model {mid!r}")
            return None
    elif mid is not None:
        console.print(
            f"[red]error:[/red] runtime {rid!r} does not use models; omit --model"
        )
        return None

    skip_keys = bound_keys_to_skip(mf.serve_schema, model_id=mid)
    model_entry = get_entry(settings.models_dir, mid) if mid else None
    hints: dict[str, str] = {}
    for spec in mf.serve_schema:
        rec = recommend(rid, spec.key, model=model_entry, specs=specs)
        if rec is None:
            continue
        hints[spec.key] = f"suggested {rec.value} ({rec.reason})"

    cid_guess = f"{rid}__{mid}__{preset}" if mid else f"{rid}__{preset}"
    result = wiz.edit_params(
        mf.serve_schema,
        title="Config setup",
        skip_keys=set(skip_keys),
        readonly_keys=set(skip_keys),
        hints=hints,
        meta=[
            MetaField(
                key="host",
                label="host",
                value="127.0.0.1",
                description="serve.host",
            ),
            MetaField(
                key="port",
                label="port",
                value="8080",
                description="serve.port",
            ),
            MetaField(
                key="preset",
                label="preset",
                value=preset,
            ),
            MetaField(
                key="config_id",
                label="config_id",
                value=cid_guess,
            ),
        ],
    )
    if result.action == "abort":
        console.print("[yellow]aborted[/yellow]")
        return None

    host_final = result.meta.get("host", "127.0.0.1").strip() or "127.0.0.1"
    preset_final = result.meta.get("preset", preset).strip() or preset
    config_id = result.meta.get("config_id", cid_guess).strip() or cid_guess
    try:
        port_final = int(result.meta.get("port", "8080").strip())
    except ValueError:
        console.print("[red]error:[/red] port must be an integer")
        return None

    params_final = apply_model_bindings(
        mf.serve_schema,
        dict(result.values),
        model_id=mid,
    )
    coerced, errors = validate_params(mf.serve_schema, params_final)
    if errors:
        for err in errors:
            console.print(f"[red]error:[/red] {err}")
        return None

    expected_id = (
        f"{rid}__{mid}__{preset_final}" if mid else f"{rid}__{preset_final}"
    )
    if config_id != expected_id:
        console.print(
            f"[yellow]note:[/yellow] saving as `{config_id}` "
            f"(differs from derived `{expected_id}`)"
        )

    out_path = configs_dir(settings) / f"{config_id}.yaml"
    doc: dict[str, Any] = {"id": config_id, "runtime": rid}
    if mid:
        doc["model"] = mid
    doc["serve"] = {
        "host": host_final,
        "port": port_final,
        "params": dict(coerced),
    }
    doc["readiness"] = {"timeout_seconds": 600}
    _atomic_write_yaml(out_path, doc)
    append_history(
        state_root(settings),
        {"action": "config-create", "id": config_id, "via": "setup"},
    )
    typer.echo(config_id)
    return config_id


@config_app.command("show")
def config_show(
    config_id: str = typer.Argument(..., help="Config id (filename stem)."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of YAML."),
) -> None:
    """Print a single resolved config (expands ${data_root} in serve.env)."""
    cfg = registry.get_config_merged(config_id)
    if cfg is None:
        console.print(f"[red]error:[/red] unknown config {config_id!r}")
        raise typer.Exit(code=1)
    console.print(f"[dim]source:[/dim] {cfg.source}")
    resolved = resolve_config_for_display(cfg, resolve(load_settings()))
    if as_json:
        typer.echo(json.dumps(resolved, indent=2))
    else:
        typer.echo(yaml.safe_dump(resolved, sort_keys=False, allow_unicode=True))


@config_app.command("validate")
def config_validate() -> None:
    """Validate every configs/*.yaml against repo manifests and script layout."""
    configs = registry.discover_configs_merged()
    if not configs:
        console.print("[yellow]warning:[/yellow] no configs/*.yaml found")
        raise typer.Exit(code=0)

    bad = 0
    scaffold = scaffold_root()
    for cfg in configs:
        errors, warnings = registry.validate_config_v2(scaffold, cfg)
        if errors:
            bad += 1
            console.print(f"[red]{cfg.id}[/red]")
            for e in errors:
                console.print(f"  - {e}")
        else:
            console.print(f"[green]ok[/green] {cfg.id}")
        for w in warnings:
            console.print(f"[yellow]warning:[/yellow] {w}")

    if bad:
        raise typer.Exit(code=1)


@config_app.command("new")
def config_new(
    runtime: str = typer.Option(..., "--runtime"),
    model: Optional[str] = typer.Option(None, "--model"),
    preset: str = typer.Option("default", "--preset"),
    port: int = typer.Option(8080, "--port"),
    host: str = typer.Option("127.0.0.1", "--host"),
    param: list[str] = typer.Option([], "--param", help="key=value (repeatable)."),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Write user/configs/<id>.yaml without prompts."""
    raw_params: dict[str, str] = {}
    for token in param:
        k, v = _parse_param(token)
        raw_params[k] = v
    do_config_new(
        runtime_id=runtime,
        model_id=model,
        preset=preset,
        port=port,
        host=host,
        params=raw_params,
        force=force,
        via="new",
    )


@config_app.command("setup")
def config_setup(
    runtime: Optional[str] = typer.Option(None, "--runtime"),
    model: Optional[str] = typer.Option(None, "--model"),
    preset: str = typer.Option("default", "--preset"),
) -> None:
    """Interactive wizard for user/configs/*.yaml."""
    cid = do_config_setup(runtime_id=runtime, model_id=model, preset=preset)
    if cid is None:
        raise typer.Exit(code=1)
