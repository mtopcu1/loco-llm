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
from llm_cli.core.lifecycle import append_history
from llm_cli.core.model_registry import get_entry, load_registry
from llm_cli.core.params import ParamSpec, validate_params
from llm_cli.core.recommendations import recommend
from llm_cli.core.repo import repo_root
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
    """Write configs/<id>.yaml and return the config id."""
    repo = repo_root()
    rt = registry.get_runtime_manifest(repo, runtime_id)
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

    coerced, errors = validate_params(rt.serve_schema, params or {})
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
    out_path = repo / "configs" / f"{cid}.yaml"
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
        "params": dict(params or {}),
    }
    doc["readiness"] = {"timeout_seconds": 600}

    _atomic_write_yaml(out_path, doc)
    append_history(repo, {"action": "config-create", "id": cid, "via": via})
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

    repo = repo_root()
    settings = resolve(load_settings())
    specs = detect_all(
        repo_root=settings.repo_root.as_posix(),
        data_root=settings.data_root.as_posix(),
    )

    manifests = registry.load_runtime_manifests(repo)
    if not manifests:
        console.print("[red]error:[/red] no runtimes found under runtimes/")
        return None

    if runtime_id is None:
        rid = wiz.select("Pick a runtime", [m.id for m in manifests])
    else:
        rid = runtime_id

    mf = registry.get_runtime_manifest(repo, rid)
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
                "`llm model pull <hf-url>` first."
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

    params_raw: dict[str, str] = {}

    def walk_specs(specs_list: list[ParamSpec]) -> None:
        model_entry = get_entry(settings.models_dir, mid) if mid else None
        for spec in specs_list:
            rec = recommend(rid, spec.key, model=model_entry, specs=specs)
            default_str = (
                rec.value
                if rec is not None
                else ("" if spec.default is None else str(spec.default))
            )
            if spec.description:
                console.print(f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}")
                if rec is not None:
                    console.print(
                        f"  [green]suggested {rec.value}[/green] "
                        f"[dim]({rec.reason})[/dim]"
                    )
            answer = wiz.text(spec.key, default=default_str or None)
            params_raw[spec.key] = answer

    common = [s for s in mf.serve_schema if s.tier == "common"]
    advanced = [s for s in mf.serve_schema if s.tier == "advanced"]
    walk_specs(common)
    if advanced and wiz.confirm(
        f"Reveal {len(advanced)} advanced parameter(s)?", default=False
    ):
        walk_specs(advanced)

    host = wiz.text("serve.host", default="127.0.0.1")
    port_s = wiz.text("serve.port", default="8080")
    preset_val = wiz.text("preset", default=preset)
    try:
        port_i = int(port_s.strip())
    except ValueError:
        console.print("[red]error:[/red] port must be an integer")
        return None

    cid_guess = (
        f"{rid}__{mid}__{preset_val}" if mid else f"{rid}__{preset_val}"
    )

    holder: dict[str, str] = {
        "runtime": rid,
        "model": mid or "(none)",
        "preset": preset_val,
        "host": host,
        "port": str(port_i),
        "config_id": cid_guess,
    }
    for k, v in params_raw.items():
        holder[f"param:{k}"] = v

    def _on_edit(label: str) -> None:
        if label == "runtime":
            console.print("[yellow]hint:[/yellow] runtime is fixed in this pass.")
            return
        if label == "model":
            console.print("[yellow]hint:[/yellow] model is fixed in this pass.")
            return
        if label == "preset":
            holder["preset"] = wiz.text("preset", default=holder["preset"])
        elif label == "host":
            holder["host"] = wiz.text("serve.host", default=holder["host"])
        elif label == "port":
            holder["port"] = wiz.text("serve.port", default=holder["port"])
        elif label == "config_id":
            holder["config_id"] = wiz.text("config id", default=holder["config_id"])
        elif label.startswith("param:"):
            key = label[len("param:") :]
            holder[label] = wiz.text(key, default=holder[label])

    def _review_rows() -> list[tuple[str, str]]:
        r = [
            ("runtime", holder["runtime"]),
            ("model", holder["model"]),
            ("preset", holder["preset"]),
            ("host", holder["host"]),
            ("port", holder["port"]),
            ("config_id", holder["config_id"]),
        ]
        for k, v in sorted(params_raw.items()):
            r.append((f"param:{k}", holder[f"param:{k}"]))
        return r

    action = wiz.review(_review_rows, on_edit=_on_edit)
    if action == wiz.ABORT_SENTINEL:
        console.print("[yellow]aborted[/yellow]")
        return None
    if action != wiz.SAVE_SENTINEL:
        return None

    preset_final = holder["preset"]
    host_final = holder["host"]
    try:
        port_final = int(holder["port"].strip())
    except ValueError:
        console.print("[red]error:[/red] port must be an integer")
        return None

    params_final = {
        k[len("param:") :]: holder[k]
        for k in holder
        if k.startswith("param:")
    }

    override_id = holder["config_id"].strip()
    expected_id = (
        f"{rid}__{mid}__{preset_final}" if mid else f"{rid}__{preset_final}"
    )
    if override_id != expected_id:
        console.print(
            f"[yellow]note:[/yellow] saving as `{override_id}` "
            f"(differs from derived `{expected_id}`)"
        )

    return do_config_new(
        runtime_id=rid,
        model_id=mid,
        preset=preset_final,
        port=port_final,
        host=host_final,
        params=params_final,
        force=True,
        via="setup",
        config_id=override_id,
    )


@config_app.command("show")
def config_show(
    config_id: str = typer.Argument(..., help="Config id (filename stem)."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of YAML."),
) -> None:
    """Print a single resolved config (expands ${data_root} in serve.env)."""
    repo = repo_root()
    cfg = registry.get_config(repo, config_id)
    if cfg is None:
        console.print(f"[red]error:[/red] unknown config {config_id!r}")
        raise typer.Exit(code=1)
    resolved = resolve_config_for_display(cfg, resolve(load_settings()))
    if as_json:
        typer.echo(json.dumps(resolved, indent=2))
    else:
        typer.echo(yaml.safe_dump(resolved, sort_keys=False, allow_unicode=True))


@config_app.command("validate")
def config_validate() -> None:
    """Validate every configs/*.yaml against repo manifests and script layout."""
    repo = repo_root()
    configs = registry.discover_configs(repo)
    if not configs:
        console.print("[yellow]warning:[/yellow] no configs/*.yaml found")
        raise typer.Exit(code=0)

    bad = 0
    for cfg in configs:
        errors, warnings = registry.validate_config_v2(repo, cfg)
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
    """Write configs/<id>.yaml without prompts."""
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
    """Interactive wizard for configs/*.yaml."""
    cid = do_config_setup(runtime_id=runtime, model_id=model, preset=preset)
    if cid is None:
        raise typer.Exit(code=1)
