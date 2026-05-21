"""`loco runtime` - manage runtime installs."""
from __future__ import annotations

import json
import os
import stat
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core import registry
from llm_cli.core.doctor import CheckStatus, check_all, requirements_for_runtime
from llm_cli.core.install_record import (
    InstallRecord,
    clear_record,
    file_sha256,
    is_installed,
    read_record,
    schema_hash,
    write_record,
)
from llm_cli.core.lifecycle import append_history, state_root
from llm_cli.core.params import derive_env_name, validate_params
from llm_cli.core.repo import scaffold_root
from llm_cli.core.scaffold import user_runtimes_dir
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core.wsl import run_runtime_bash

console = Console()
runtime_app = typer.Typer(
    help="Manage runtime installs (list/info/install/uninstall/rebuild)."
)

_LAST_RUNTIME_SETUP_ID: str | None = None


def last_runtime_setup_id() -> str | None:
    """Last runtime id produced by `interactive_runtime_setup`, if any."""
    return _LAST_RUNTIME_SETUP_ID


_DEFAULT_HEALTHCHECK_SH = """#!/usr/bin/env bash
set -euo pipefail
HOST="${LLM_SERVE_HOST:-127.0.0.1}"
curl -fsS -o /dev/null "http://${HOST}:${LLM_SERVE_PORT}/v1/models"
"""

_CUSTOM_PARAMS_YAML = """extra_args:
  type: string
  env: LLM_EXTRA_ARGS
  tier: common
  description: "Pass-through flags appended to your serve command."
"""


def _atomic_write_runtime(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".rt-", suffix=path.suffix or ".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    if executable:
        try:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass


def _serve_script_body(invocation: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "INVOCATION_LINE=$(cat <<'LLM_SERVE_INV_EOF'\n"
        f"{invocation}\n"
        "LLM_SERVE_INV_EOF\n"
        ")\n"
        'bash -eo pipefail -c "$INVOCATION_LINE"\n'
    )


def _run_install_for_id(
    runtime_id: str,
    *,
    param: list[str] | None = None,
    yes: bool = False,
) -> None:
    settings = _settings()
    _install_impl(
        settings=settings,
        runtime_id=runtime_id,
        param=list(param or []),
        yes=yes,
    )


def _runtime_setup_preset() -> str:
    from llm_cli.core import wizards as wiz

    settings = _settings()
    manifests = [
        m for m in registry.load_runtime_manifests_merged() if m.kind == "official"
    ]
    if not manifests:
        console.print("[red]error:[/red] no official runtimes found in runtimes/")
        raise typer.Exit(code=1)
    picked = wiz.select("Pick a preset", [m.id for m in manifests])
    _run_install_for_id(picked, yes=False)
    return picked


def _runtime_setup_custom() -> str:
    import subprocess

    from llm_cli.core import wizards as wiz

    settings = _settings()

    def _slug_ok(v: str) -> str | None:
        t = v.strip()
        if not t:
            return "id is required"
        core = t.replace("-", "").replace("_", "")
        if not core.isalnum():
            return "id must be a slug (letters, digits, dashes, underscores)"
        return None

    rt_id = wiz.text("Runtime id (slug, e.g. 'vllm-custom')", validate=_slug_ok).strip()
    rt_dir = user_runtimes_dir(settings) / rt_id
    if registry.get_runtime_merged(rt_id) is not None:
        console.print(
            f"[red]error:[/red] runtime {rt_id!r} already exists. "
            f"Pick a different id, or use `loco runtime uninstall {rt_id} --purge` "
            f"if you own a user-layer copy."
        )
        raise typer.Exit(code=1)
    if rt_dir.exists():
        console.print(
            f"[red]error:[/red] runtime {rt_id!r} already exists at {rt_dir}. "
            f"`loco runtime uninstall {rt_id} --purge` first, or pick a different id."
        )
        raise typer.Exit(code=1)

    display_name = wiz.text("Display name", default=rt_id)
    formats = wiz.checkbox(
        "Accepts which model formats?",
        ["gguf", "safetensors-dir", "none (no model needed)"],
    )
    if "none (no model needed)" in formats:
        accepts_formats: list[str] = []
    else:
        accepts_formats = [f for f in formats if f != "none (no model needed)"]

    mode = wiz.select(
        "Serve command",
        ["Template (we wrap in bash)", "Editor (full control)"],
    )
    default_inv = (
        'your-server "$LLM_MODEL_PATH" --host "$LLM_SERVE_HOST" '
        '--port "$LLM_SERVE_PORT" $LLM_EXTRA_ARGS'
    )
    if mode.startswith("Template"):
        invocation = wiz.text("Bare invocation line", default=default_inv)
        serve_sh = _serve_script_body(invocation)
    else:
        import tempfile as tf

        editor = os.environ.get("EDITOR", "nano")
        with tf.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".sh",
            delete=False,
        ) as fh:
            fh.write(_serve_script_body(default_inv))
            tmp_path = fh.name
        rc = subprocess.call([editor, tmp_path])
        if rc != 0:
            Path(tmp_path).unlink(missing_ok=True)
            console.print("[red]error:[/red] editor exited non-zero; aborting.")
            raise typer.Exit(code=1)
        serve_sh = Path(tmp_path).read_text(encoding="utf-8")
        Path(tmp_path).unlink(missing_ok=True)

    req_cmd = wiz.text(
        "Add a `requires:` check? (command to run; empty to skip)",
        default="",
    )
    requires_entries: list[dict[str, Any]] = []
    if req_cmd.strip():
        req_regex = wiz.text("version regex", default=r"([\d.]+)")
        req_min = wiz.text("minimum version (empty for none)", default="")
        req_hint = wiz.text("install hint", default="")
        rid_key = req_cmd.split()[0]
        verify: dict[str, Any] = {
            "cmd": req_cmd.strip(),
            "version_regex": req_regex.strip(),
        }
        if req_min.strip():
            verify["min"] = req_min.strip()
        requires_entries.append(
            {
                "id": rid_key,
                "verify": verify,
                "install_hint": req_hint,
            }
        )

    manifest_doc: dict[str, Any] = {
        "id": rt_id,
        "display_name": display_name,
        "kind": "custom",
        "accepts_formats": accepts_formats,
        "requires": requires_entries,
    }

    rt_dir.mkdir(parents=True, exist_ok=False)
    manifest_yaml = yaml.safe_dump(manifest_doc, sort_keys=False, allow_unicode=True)
    _atomic_write_runtime(rt_dir / "manifest.yaml", manifest_yaml)
    _atomic_write_runtime(rt_dir / "params.yaml", _CUSTOM_PARAMS_YAML)
    _atomic_write_runtime(rt_dir / "serve.sh", serve_sh, executable=True)
    _atomic_write_runtime(rt_dir / "healthcheck.sh", _DEFAULT_HEALTHCHECK_SH, executable=True)

    rec_disc = registry.get_runtime_merged(rt_id)
    if rec_disc is None:
        console.print("[red]error:[/red] failed to load new runtime record")
        raise typer.Exit(code=1)
    layout_errs = registry.validate_runtime_layout(rec_disc)
    if layout_errs:
        for err in layout_errs:
            console.print(f"[red]layout:[/red] {err}")
        raise typer.Exit(code=1)

    params_data = yaml.safe_load(_CUSTOM_PARAMS_YAML) or {}
    record = InstallRecord(
        runtime_id=rt_id,
        installed_at=_utc_now_iso(),
        build_params={},
        build_sh_sha256="",
        verify_passed=None,
        schema_hash=schema_hash(params_data),
        kind="custom",
    )
    write_record(settings.runtimes_dir, record)
    append_history(
        state_root(settings),
        {"action": "runtime-setup", "id": rt_id, "kind": "custom"},
    )
    console.print(f"[green]wrote[/green] user/runtimes/{rt_id}/manifest.yaml")
    console.print(f"[green]wrote[/green] user/runtimes/{rt_id}/params.yaml")
    console.print(f"[green]wrote[/green] user/runtimes/{rt_id}/serve.sh")
    console.print(f"[green]wrote[/green] user/runtimes/{rt_id}/healthcheck.sh")
    console.print(f"[green]wrote[/green] {settings.runtimes_dir / rt_id / '.installed'}")
    console.print(f"\nNext: loco config setup --runtime {rt_id}")
    typer.echo(rt_id)
    return rt_id


def interactive_runtime_setup() -> str | None:
    global _LAST_RUNTIME_SETUP_ID
    from llm_cli.core import wizards as wiz

    try:
        branch = wiz.select(
            "Runtime setup",
            [
                "Preset — install an official runtime",
                "Custom — register an existing install",
            ],
        )
    except KeyboardInterrupt:
        console.print()
        return None
    if branch.startswith("Preset"):
        try:
            rid = _runtime_setup_preset()
        except typer.Exit:
            raise
    else:
        try:
            rid = _runtime_setup_custom()
        except typer.Exit:
            raise
    _LAST_RUNTIME_SETUP_ID = rid
    return rid


def _settings() -> Settings:
    return resolve(load_settings())


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_param_flag(token: str) -> tuple[str, str]:
    if "=" not in token:
        raise typer.BadParameter(f"--param must be key=value (got {token!r})")
    key, value = token.split("=", 1)
    key = key.strip()
    if not key:
        raise typer.BadParameter("--param key cannot be empty")
    return key, value.strip()


def _resolve_build_params(
    runtime_id: str,
    schema: list[Any],
    *,
    flags: list[str],
    yes: bool,
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for token in flags:
        key, value = _parse_param_flag(token)
        raw[key] = value

    if not yes and schema:
        from llm_cli.core import wizards as wiz

        pre_values = {k: str(v) for k, v in raw.items()}
        result = wiz.edit_params(
            schema,
            title=f"Build params: {runtime_id}",
            values=pre_values,
        )
        if result.action == "abort":
            console.print("[yellow]aborted[/yellow]")
            raise typer.Exit(code=1)
        raw.update(result.values)

    coerced, errors = validate_params(schema, raw)
    if errors:
        for error in errors:
            console.print(f"[red]error:[/red] {error}")
        raise typer.Exit(code=1)
    return coerced


def _build_env(
    runtime_id: str, schema: list[Any], build_params: dict[str, Any]
) -> dict[str, str]:
    env: dict[str, str] = {}
    for spec in schema:
        if spec.key not in build_params:
            continue
        name = derive_env_name(spec, runtime_id=runtime_id, scope="build")
        env[name] = str(build_params[spec.key])
    return env


def _run_build_script(
    *,
    settings: Settings,
    runtime_path: Path,
    env: dict[str, str],
) -> int:
    """Run build.sh in the runtime asset directory; patch point for tests."""
    return run_runtime_bash(settings, runtime_path, "build.sh", extra_env=env)


def _run_verify_script(
    *,
    settings: Settings,
    runtime_path: Path,
    env: dict[str, str],
) -> int | None:
    """Run verify.sh if present; patch point for tests."""
    if not (runtime_path / "verify.sh").is_file():
        return None
    return run_runtime_bash(settings, runtime_path, "verify.sh", extra_env=env)


def _pre_flight(runtime_id: str, build_params: dict[str, Any]) -> None:
    scaffold = scaffold_root()
    requirements = requirements_for_runtime(scaffold, runtime_id, build_params=build_params)
    if not requirements:
        return

    results = check_all(requirements)
    bad = [r for r in results if r.status is not CheckStatus.OK]
    if not bad:
        return

    for result in bad:
        hint = result.requirement.install_hint or "install manually"
        console.print(
            f"[red]missing:[/red] {result.requirement.id} "
            f"({result.status.value}). hint: {hint}"
        )
    raise typer.Exit(code=1)


def _get_runtime_manifest(runtime_id: str) -> registry.RuntimeManifest:
    manifest = registry.get_runtime_manifest_merged(runtime_id)
    if manifest is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    return manifest


def _install_impl(
    *,
    settings: Settings,
    runtime_id: str,
    param: list[str],
    yes: bool,
) -> InstallRecord:
    manifest = _get_runtime_manifest(runtime_id)
    runtime_rec = registry.get_runtime_merged(runtime_id)
    if runtime_rec is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    if manifest.kind == "custom":
        console.print(
            f"[red]error:[/red] runtime {runtime_id!r} is kind: custom — it has no "
            "build step. Use `loco runtime setup` to re-register or edit files under "
            f"{manifest.path}."
        )
        raise typer.Exit(code=1)
    build_params = _resolve_build_params(
        runtime_id, manifest.build_schema, flags=param, yes=yes
    )
    _pre_flight(runtime_id, build_params)

    build_env = _build_env(runtime_id, manifest.build_schema, build_params)
    build_rc = _run_build_script(
        settings=settings, runtime_path=runtime_rec.path, env=build_env
    )
    if build_rc != 0:
        console.print(f"[red]build failed[/red] (exit {build_rc})")
        raise typer.Exit(code=build_rc)

    verify_rc = _run_verify_script(
        settings=settings, runtime_path=runtime_rec.path, env=build_env
    )
    if verify_rc not in (None, 0):
        console.print(f"[red]verify failed[/red] (exit {verify_rc})")
        raise typer.Exit(code=verify_rc)

    record = InstallRecord(
        runtime_id=runtime_id,
        installed_at=_utc_now_iso(),
        build_params=build_params,
        build_sh_sha256=file_sha256(manifest.path / "build.sh"),
        verify_passed=True if verify_rc == 0 else None,
        schema_hash=schema_hash(manifest.raw.get("build") or {}),
        kind=manifest.kind,
    )
    write_record(settings.runtimes_dir, record)
    append_history(
        state_root(settings),
        {
            "action": "runtime-install",
            "id": runtime_id,
            "build_params": build_params,
        },
    )
    return record


@runtime_app.command("setup", help="Interactive wizard to install or register a runtime.")
def runtime_setup_command() -> None:
    try:
        rid = interactive_runtime_setup()
    except typer.Exit:
        raise
    if rid is None:
        console.print("[yellow]aborted[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]done[/green] runtime {rid}")


@runtime_app.command("list", help="List runtimes with install state.")
def runtime_list(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    settings = _settings()
    manifests = registry.load_runtime_manifests_merged()

    rows: list[dict[str, Any]] = []
    for manifest in manifests:
        record = read_record(settings.runtimes_dir, manifest.id)
        rows.append(
            {
                "id": manifest.id,
                "display_name": manifest.display_name,
                "official": manifest.official,
                "installed": record is not None,
                "installed_at": record.installed_at if record else None,
                "build_params": dict(record.build_params) if record else None,
            }
        )

    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return

    table = Table(title="Runtimes")
    table.add_column("ID")
    table.add_column("Display")
    table.add_column("Official")
    table.add_column("Installed")
    table.add_column("Build params")
    for row in rows:
        build_params = row["build_params"]
        params_text = (
            ", ".join(f"{k}={v}" for k, v in build_params.items())
            if build_params
            else "-"
        )
        table.add_row(
            row["id"],
            row["display_name"],
            "yes" if row["official"] else "no",
            "yes" if row["installed"] else "no",
            params_text,
        )
    console.print(table)


@runtime_app.command("info", help="Show manifest, install record, and drift.")
def runtime_info(runtime_id: str = typer.Argument(...)) -> None:
    settings = _settings()
    manifest = _get_runtime_manifest(runtime_id)
    rec = registry.get_runtime_merged(runtime_id)

    console.print(f"[bold]{manifest.id}[/bold] - {manifest.display_name}")
    if rec is not None:
        console.print(f"source: {rec.source}")
    console.print(f"official: {'yes' if manifest.official else 'no'}")
    if manifest.description:
        console.print(f"description: {manifest.description}")

    if manifest.build_schema:
        console.print("\n[bold]build params:[/bold]")
        for spec in manifest.build_schema:
            line = f"  - {spec.key} ({spec.type.value})"
            if spec.required:
                line += " required"
            console.print(line)

    if manifest.serve_schema:
        console.print("\n[bold]serve params:[/bold]")
        for spec in manifest.serve_schema:
            line = f"  - {spec.key} ({spec.type.value})"
            if spec.required:
                line += " required"
            console.print(line)

    record = read_record(settings.runtimes_dir, manifest.id)
    if record is None:
        console.print("\n[yellow]not installed[/yellow]")
        console.print(f"hint: loco runtime install {manifest.id}")
        return

    console.print("\n[bold]install:[/bold] [green]installed[/green]")
    console.print(f"installed_at: {record.installed_at}")
    console.print(f"verify_passed: {record.verify_passed}")
    if record.build_params:
        params = ", ".join(f"{k}={v}" for k, v in record.build_params.items())
        console.print(f"build_params: {params}")

    current_sha = file_sha256(manifest.path / "build.sh")
    if record.build_sh_sha256 and current_sha and current_sha != record.build_sh_sha256:
        console.print(
            "[yellow]drift:[/yellow] build.sh has changed since install "
            f"({record.build_sh_sha256[:8]} -> {current_sha[:8]})"
        )

    current_schema = schema_hash(manifest.raw.get("build") or {})
    if record.schema_hash and current_schema and current_schema != record.schema_hash:
        console.print(
            "[yellow]drift:[/yellow] build schema changed since install; "
            f"run `loco runtime rebuild {manifest.id} --reset` to refresh"
        )


@runtime_app.command("install", help="Install a runtime.")
def runtime_install(
    runtime_id: str = typer.Argument(...),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults; skip prompts."),
) -> None:
    settings = _settings()
    record = _install_impl(
        settings=settings, runtime_id=runtime_id, param=list(param), yes=yes
    )
    summary = ", ".join(f"{k}={v}" for k, v in record.build_params.items())
    console.print(f"[green]installed[/green] {runtime_id} ({summary or 'no params'})")


@runtime_app.command(
    "uninstall", help="Remove a runtime's install marker and optionally artifacts."
)
def runtime_uninstall(
    runtime_id: str = typer.Argument(...),
    purge: bool = typer.Option(False, "--purge", help="Also delete the install directory."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompts."),
) -> None:
    settings = _settings()
    runtime_dir = settings.runtimes_dir / runtime_id

    if not is_installed(settings.runtimes_dir, runtime_id):
        console.print(
            f"[yellow]nothing to uninstall:[/yellow] {runtime_id} is not installed"
        )
        if not purge or not runtime_dir.exists():
            return

    if not yes:
        prompt = (
            f"Purge {runtime_dir}? (all build artifacts will be deleted)"
            if purge
            else f"Remove install marker for {runtime_id}?"
        )
        from llm_cli.core import wizards as wiz

        if not wiz.confirm(prompt, default=False):
            console.print("aborted")
            raise typer.Exit(code=1)

    clear_record(settings.runtimes_dir, runtime_id)
    if purge and runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    append_history(
        state_root(settings),
        {"action": "runtime-uninstall", "id": runtime_id, "purge": purge},
    )
    console.print(
        f"[green]uninstalled[/green] {runtime_id}" + (" (purged)" if purge else "")
    )


@runtime_app.command(
    "rebuild", help="Reinstall a runtime; reuse stored build params unless --reset."
)
def runtime_rebuild(
    runtime_id: str = typer.Argument(...),
    reset: bool = typer.Option(False, "--reset", help="Discard stored params."),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults; skip prompts."),
) -> None:
    settings = _settings()
    mf = registry.get_runtime_manifest_merged(runtime_id)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    if mf.kind == "custom":
        console.print(
            f"[red]error:[/red] rebuild applies to official runtimes only "
            f"({runtime_id!r} is kind: custom)"
        )
        raise typer.Exit(code=1)

    record = read_record(settings.runtimes_dir, runtime_id)

    flags: list[str] = []
    if record is not None and not reset:
        flags.extend(f"{key}={value}" for key, value in record.build_params.items())
    flags.extend(param)

    clear_record(settings.runtimes_dir, runtime_id)
    new_record = _install_impl(
        settings=settings, runtime_id=runtime_id, param=flags, yes=yes
    )
    append_history(
        state_root(settings), {"action": "runtime-rebuild", "id": runtime_id, "reset": reset}
    )
    summary = ", ".join(f"{k}={v}" for k, v in new_record.build_params.items())
    console.print(f"[green]rebuilt[/green] {runtime_id} ({summary or 'no params'})")
