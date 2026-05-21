"""`loco model` — list/info/pull/add/uninstall against $LLM_MODELS/registry.json."""
from __future__ import annotations

import json as _json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.hf_client import fetch_repo_revision
from llm_cli.core.hf_url import HFUrlError, parse_hf_url
from llm_cli.core.model_resolve import build_artifact
from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    LocalSource,
    Metadata,
    RegistryEntry,
    encode_entry,
    get_entry,
    load_registry,
    remove_entry,
    upsert_entry,
)
from llm_cli.core.model_pull import (
    DuplicateModelRegistrationError,
    PullModelError,
    hf_download,
    pull_hf_url_model_id,
)
from llm_cli.core.settings import load_settings, resolve

console = Console()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

model_app = typer.Typer(help="Manage models (list/info/pull/add/uninstall).")


def _models_dir() -> Path:
    return resolve(load_settings()).models_dir


@model_app.command("list", help="List models registered in $LLM_MODELS/registry.json.")
def model_list(as_json: bool = typer.Option(False, "--json")) -> None:
    models_dir = _models_dir()
    reg = load_registry(models_dir)
    if as_json:
        typer.echo(
            _json.dumps({k: encode_entry(v) for k, v in reg.items()}, indent=2)
        )
        return
    if not reg:
        console.print("[dim]no models registered[/dim]")
        return
    table = Table(title="Models")
    table.add_column("ID")
    table.add_column("Format")
    table.add_column("Source")
    table.add_column("Size")
    table.add_column("Present")
    for mid, e in sorted(reg.items()):
        present = (models_dir / mid / e.artifact.primary).exists()
        table.add_row(
            mid,
            e.format,
            e.source.kind,
            f"{e.artifact.total_size_bytes}",
            "yes" if present else "[red]no[/red]",
        )
    console.print(table)


@model_app.command("info", help="Show a registered model's full entry.")
def model_info(
    model_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    models_dir = _models_dir()
    e = get_entry(models_dir, model_id)
    if e is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    if as_json:
        typer.echo(_json.dumps({model_id: encode_entry(e)}, indent=2))
        return
    console.print(f"[bold]{e.id}[/bold] — {e.metadata.display_name or '(no display name)'}")
    console.print(f"  format: {e.format}")
    console.print(f"  source.kind: {e.source.kind}")
    if hasattr(e.source, "repo"):
        console.print(f"  source.repo: {e.source.repo}@{e.source.revision}")
        if e.source.include:
            console.print(f"  source.include: {list(e.source.include)}")
    if hasattr(e.source, "original_path"):
        console.print(f"  source.original_path: {e.source.original_path}")
    console.print(f"  artifact.primary: {e.artifact.primary}")
    console.print(
        f"  artifact.files: {len(e.artifact.files)} file(s), "
        f"{e.artifact.total_size_bytes} bytes"
    )
    if e.metadata.license:
        console.print(f"  metadata.license: {e.metadata.license}")
    if e.metadata.ctx_length:
        console.print(f"  metadata.ctx_length: {e.metadata.ctx_length}")
    console.print(f"  installed_at: {e.installed_at}")


def do_model_pull(url: str, **kwargs: Any) -> str:
    """Programmatic HF URL pull (used by `loco setup` chain)."""
    return pull_hf_url_model_id(url, **kwargs)


@model_app.command("pull", help="Pull a model from HF (URL) or re-pull an existing id.")
def model_pull(
    target: str = typer.Argument(..., help="HF URL or registered model id."),
    fmt: Optional[str] = typer.Option(
        None, "--format", help="Override format (gguf|safetensors-dir)."
    ),
    include: list[str] = typer.Option(
        [], "--include", help="hf download --include pattern (repeatable)."
    ),
    exclude: list[str] = typer.Option(
        [], "--exclude", help="hf download --exclude pattern (repeatable)."
    ),
    id_override: Optional[str] = typer.Option(
        None, "--id", help="Override derived model id."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing entry."),
) -> None:
    models_dir = _models_dir()

    try:
        parsed = parse_hf_url(target)
    except HFUrlError:
        parsed = None

    if parsed is not None:
        try:
            mid = pull_hf_url_model_id(
                target,
                fmt=fmt,
                include=list(include) if include else None,
                exclude=list(exclude) if exclude else None,
                id_override=id_override,
                force=force,
            )
        except PullModelError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"[green]registered[/green] {mid}")
        console.print(
            f"  next: edit your config to use `model: {mid}` and "
            "`gguf_path: ${model_path}`"
        )
        return

    # Treat target as an existing id.
    existing = get_entry(models_dir, target)
    if existing is None:
        console.print(
            f"[red]error:[/red] {target!r} is neither a valid HF URL nor a registered model id"
        )
        raise typer.Exit(code=1)
    if not isinstance(existing.source, HFSource):
        console.print(
            f"[red]error:[/red] {target!r} is a local-source model; "
            "re-pull only applies to HF entries"
        )
        raise typer.Exit(code=1)
    target_dir = models_dir / existing.id
    rc = hf_download(
        existing.source.repo,
        existing.source.revision,
        list(existing.source.include),
        list(existing.source.exclude),
        target_dir,
    )
    if rc != 0:
        console.print(f"[red]error:[/red] hf download failed (exit {rc})")
        raise typer.Exit(code=rc)
    artifact = build_artifact(target_dir, existing.format)
    refreshed = RegistryEntry(
        id=existing.id,
        format=existing.format,
        source=existing.source,
        artifact=Artifact(
            primary=artifact.primary,
            files=artifact.files,
            total_size_bytes=artifact.total_size_bytes,
            sha256=existing.artifact.sha256,
        ),
        metadata=existing.metadata,
        installed_at=_utc_now_iso(),
    )
    upsert_entry(models_dir, refreshed)
    console.print(f"[green]refreshed[/green] {existing.id}")


def _symlink_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.symlink(src, dst)
    except (OSError, NotImplementedError):
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        console.print(f"[yellow][info][/yellow] symlink unavailable; copied {src} -> {dst}")


@model_app.command("add", help="Register pre-existing local weights under a model id.")
def model_add(
    model_id: str = typer.Argument(...),
    path: Path = typer.Argument(...),
    fmt: str = typer.Option(..., "--format", help="gguf | safetensors-dir"),
) -> None:
    if not path.exists():
        console.print(f"[red]error:[/red] path does not exist: {path}")
        raise typer.Exit(code=1)
    models_dir = _models_dir()
    target = models_dir / model_id
    target.mkdir(parents=True, exist_ok=True)

    if fmt == "gguf":
        if path.is_file():
            _symlink_or_copy(path, target / path.name)
        elif path.is_dir():
            for entry in sorted(path.iterdir()):
                if entry.suffix.lower() == ".gguf":
                    _symlink_or_copy(entry, target / entry.name)
        else:
            console.print(f"[red]error:[/red] unsupported gguf path: {path}")
            raise typer.Exit(code=1)
    elif fmt == "safetensors-dir":
        if not path.is_dir():
            console.print(
                f"[red]error:[/red] safetensors-dir requires a directory: {path}"
            )
            raise typer.Exit(code=1)
        if not (path / "config.json").is_file():
            console.print(
                f"[red]error:[/red] safetensors-dir missing config.json: {path}"
            )
            raise typer.Exit(code=1)
        for entry in sorted(path.iterdir()):
            _symlink_or_copy(entry, target / entry.name)
    else:
        console.print(f"[red]error:[/red] unknown --format {fmt!r}")
        raise typer.Exit(code=1)

    try:
        artifact = build_artifact(target, fmt)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    entry = RegistryEntry(
        id=model_id,
        format=fmt,
        source=LocalSource(original_path=str(path.resolve())),
        artifact=artifact,
        metadata=Metadata(display_name=model_id),
        installed_at=_utc_now_iso(),
    )
    upsert_entry(models_dir, entry)
    console.print(f"[green]registered[/green] {model_id}")


@model_app.command("uninstall", help="Remove a registered model.")
def model_uninstall(
    model_id: str = typer.Argument(...),
    purge: bool = typer.Option(False, "--purge", help="Also delete $LLM_MODELS/<id>/."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    models_dir = _models_dir()
    if get_entry(models_dir, model_id) is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    if not yes:
        msg = (
            f"Purge {models_dir / model_id}? (removes weights/symlinks)"
            if purge
            else f"Remove registry entry {model_id!r}?"
        )
        from llm_cli.core import wizards as wiz

        if not wiz.confirm(msg, default=False):
            console.print("aborted")
            raise typer.Exit(code=1)
    remove_entry(models_dir, model_id)
    if purge:
        target = models_dir / model_id
        if target.exists():
            shutil.rmtree(target)
    console.print(f"[green]uninstalled[/green] {model_id}")
