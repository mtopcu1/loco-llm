"""Interactive runtime setup (preset install and custom registration)."""
from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core import runtime_install as rt_install
from llm_cli.core.install_record import InstallRecord, schema_hash, write_record
from llm_cli.core.lifecycle import append_history, state_root
from llm_cli.core.runtime_install import RuntimeInstallError
from llm_cli.core.scaffold import user_runtimes_dir
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core.time import utc_now_iso

console = Console()

_LAST_RUNTIME_SETUP_ID: str | None = None

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


def last_runtime_setup_id() -> str | None:
    """Last runtime id produced by `interactive_runtime_setup`, if any."""
    return _LAST_RUNTIME_SETUP_ID


def _settings() -> Settings:
    return resolve(load_settings())


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


def run_install_for_id(
    runtime_id: str,
    *,
    param: list[str] | None = None,
    yes: bool = False,
) -> None:
    """Install a preset runtime (patch point for setup integration tests)."""
    settings = _settings()
    try:
        rt_install.install_runtime(
            runtime_id, param=list(param or []), yes=yes, settings=settings
        )
    except RuntimeInstallError as exc:
        console.print(f"[red]error:[/red] {exc.message}")
        raise typer.Exit(code=exc.exit_code) from exc


def _runtime_setup_preset() -> str:
    from llm_cli.core import wizards as wiz

    manifests = [
        m for m in registry.load_runtime_manifests_merged() if m.kind == "official"
    ]
    if not manifests:
        console.print("[red]error:[/red] no official runtimes found in runtimes/")
        raise typer.Exit(code=1)
    picked = wiz.select("Pick a preset", [m.id for m in manifests])
    run_install_for_id(picked, yes=False)
    return picked


def _runtime_setup_custom() -> str:
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
        installed_at=utc_now_iso(),
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
