"""`llm model` — list/info/pull/add/uninstall against $LLM_MODELS/registry.json."""
from __future__ import annotations

import hashlib
import json as _json
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run as _subprocess_run
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.hf_client import HFApiError, fetch_repo_revision
from llm_cli.core.hf_url import HFUrlError, parse_hf_url
from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    encode_entry,
    get_entry,
    load_registry,
    upsert_entry,
)
from llm_cli.core.model_resolve import (
    FormatInferenceError,
    build_artifact,
    derive_model_id,
    infer_format,
)
from llm_cli.core.settings import load_settings, resolve

console = Console()
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


def hf_download(
    repo: str,
    revision: str,
    include: list[str],
    exclude: list[str],
    target_dir: Path,
) -> int:
    """Invoke `hf download` as a subprocess. Patched in tests."""
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo, "--revision", revision, "--local-dir", str(target_dir)]
    for pat in include:
        cmd += ["--include", pat]
    for pat in exclude:
        cmd += ["--exclude", pat]
    result = _subprocess_run(cmd, check=False)
    return result.returncode


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _verify_sha256(target_dir: Path, expected: dict[str, str]) -> list[str]:
    errs: list[str] = []
    for rel, want in expected.items():
        p = target_dir / rel
        if not p.is_file():
            errs.append(f"{rel}: file missing on disk")
            continue
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
        got = h.hexdigest()
        if got != want:
            errs.append(f"{rel}: sha256 mismatch (got {got[:8]}…, want {want[:8]}…)")
    return errs


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
            info = fetch_repo_revision(parsed.repo, revision=parsed.revision)
        except HFApiError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        inferred = None
        if not (fmt and include):
            try:
                inferred = infer_format(
                    parsed, [s.rfilename for s in info.siblings]
                )
            except FormatInferenceError as exc:
                console.print(f"[red]error:[/red] {exc}")
                raise typer.Exit(code=1) from exc

        chosen_format = fmt or (inferred.format if inferred else "")
        chosen_include = list(include or (inferred.include if inferred else ()))
        chosen_exclude = list(exclude)

        if not chosen_format:
            console.print("[red]error:[/red] could not determine format; pass --format")
            raise typer.Exit(code=1)

        mid = id_override or derive_model_id(parsed)
        target_dir = models_dir / mid
        if get_entry(models_dir, mid) is not None and not force:
            console.print(
                f"[red]error:[/red] {mid!r} already registered; "
                f"use `--force` to overwrite or `llm model uninstall {mid}` first"
            )
            raise typer.Exit(code=1)

        rc = hf_download(
            parsed.repo, parsed.revision, chosen_include, chosen_exclude, target_dir
        )
        if rc != 0:
            console.print(f"[red]error:[/red] hf download failed (exit {rc})")
            raise typer.Exit(code=rc)

        artifact = build_artifact(target_dir, chosen_format)
        sha_map = {
            s.rfilename: s.lfs_sha256
            for s in info.siblings
            if s.lfs_sha256 and s.rfilename in artifact.files
        }
        bad = _verify_sha256(target_dir, sha_map)
        if bad:
            for line in bad:
                console.print(f"[red]sha256:[/red] {line}")
            raise typer.Exit(code=1)
        artifact_with_hashes = Artifact(
            primary=artifact.primary,
            files=artifact.files,
            total_size_bytes=artifact.total_size_bytes,
            sha256=sha_map,
        )

        entry = RegistryEntry(
            id=mid,
            format=chosen_format,
            source=HFSource(
                repo=parsed.repo,
                revision=parsed.revision,
                include=tuple(chosen_include),
                exclude=tuple(chosen_exclude),
            ),
            artifact=artifact_with_hashes,
            metadata=Metadata(
                display_name=info.repo,
                license=info.license,
                ctx_length=None,
            ),
            installed_at=_utc_now_iso(),
        )
        upsert_entry(models_dir, entry)
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
