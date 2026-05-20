"""`llm doctor` — verify external requirements; `llm doctor render-requirements` regenerates the markdown."""
from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.doctor import (
    CheckStatus,
    check_all,
    load_requirements,
    run_scope,
    run_quick_checks,
    systemd_linger_advisory,
)
from llm_cli.core.repo import scaffold_root
from llm_cli.core.scaffold import scaffold_root as install_root

console = Console()


def _check_on_release_tag() -> tuple[str, str, str]:
    """Return (id, status, detail) for the head-on-tag check."""
    try:
        root = install_root()
    except RuntimeError as exc:
        return ("install-channel", "error", str(exc))
    try:
        subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True,
            check=True,
            timeout=2,
        )
        return ("install-channel", "ok", "on a release tag")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return (
            "install-channel",
            "warn",
            "not on a release tag — run `llm update` to re-anchor to the latest stable tag",
        )


def _print_install_channel_check() -> None:
    cid, status, detail = _check_on_release_tag()
    if status == "ok":
        return
    if status == "warn":
        console.print(f"[yellow]warning ({cid}):[/yellow] {detail}")
        return
    console.print(f"[red]error ({cid}):[/red] {detail}")
doctor_app = typer.Typer(
    name="doctor",
    help="Verify external requirements (CUDA driver, Python, hf CLI, ...).",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _requirements_yaml(repo: Path) -> Path:
    path = repo / "requirements.yaml"
    if not path.is_file():
        console.print(f"[red]error:[/red] requirements.yaml not found at {path}")
        raise typer.Exit(code=1)
    return path


_STATUS_STYLES = {
    CheckStatus.OK: "green",
    CheckStatus.OUTDATED: "yellow",
    CheckStatus.MISSING: "red",
    CheckStatus.UNKNOWN: "magenta",
    CheckStatus.ERROR: "red",
}


@doctor_app.callback()
def doctor(
    ctx: typer.Context,
    runtime: str | None = typer.Option(
        None, "--runtime", help="Scope to a single runtime's requirements."
    ),
    all_runtimes: bool = typer.Option(
        False, "--all", help="Include every runtime's deps (installed or not)."
    ),
    quick: bool = typer.Option(
        False,
        "--quick",
        help="Fast checks only (settings, scaffold dir, requirements.yaml).",
    ),
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="Run a specialized doctor scope (currently: dashboard).",
    ),
) -> None:
    """Run requirement checks: universal + runtime-scoped extras."""
    if ctx.invoked_subcommand is not None:
        return

    if quick:
        ok, detail = run_quick_checks()
        _print_install_channel_check()
        if ok:
            console.print("[green]quick checks passed[/green]")
            return
        console.print(f"[red]error:[/red] {detail}")
        raise typer.Exit(code=1)

    if scope is not None:
        if scope != "dashboard":
            console.print(f"[red]error:[/red] unknown scope {scope!r} (supported: dashboard)")
            raise typer.Exit(code=1)
        results = run_scope(scope)
        table = Table(title=f"Doctor Scope: {scope}")
        table.add_column("Check", no_wrap=True)
        table.add_column("Status")
        table.add_column("Detail", overflow="fold")
        bad = 0
        for result in results:
            status = result.status
            style = {
                "ok": "green",
                "info": "cyan",
                "warning": "yellow",
                "error": "red",
            }.get(status, "white")
            if status == "error":
                bad += 1
            table.add_row(
                result.name,
                f"[{style}]{status}[/{style}]",
                result.message,
            )
        console.print(table)
        if bad:
            raise typer.Exit(code=1)
        return

    repo = scaffold_root()
    universal = load_requirements(_requirements_yaml(repo))

    from llm_cli.core.doctor import (
        requirements_for_all_runtimes,
        requirements_for_runtime,
    )
    from llm_cli.core.settings import load_settings, resolve as _resolve

    try:
        settings = _resolve(load_settings())
    except Exception as exc:  # noqa: BLE001 - surface settings issues as doctor failures.
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    extras: list = []
    if runtime is not None:
        from llm_cli.core import registry as _registry
        from llm_cli.core.install_record import read_record

        mf = _registry.get_runtime_manifest_merged(runtime)
        if mf is None:
            console.print(f"[red]error:[/red] unknown runtime {runtime!r}")
            raise typer.Exit(code=1)

        rec = read_record(settings.runtimes_dir, runtime)
        build_params = dict(rec.build_params) if rec is not None else {}
        extras = requirements_for_runtime(repo, runtime, build_params=build_params)
    elif all_runtimes:
        extras = requirements_for_all_runtimes(repo, settings.runtimes_dir, installed_only=False)
    else:
        extras = requirements_for_all_runtimes(repo, settings.runtimes_dir, installed_only=True)

    seen = {req.id for req in universal}
    merged = list(universal)
    for req in extras:
        if req.id in seen:
            continue
        seen.add(req.id)
        merged.append(req)

    results = check_all(merged)

    table = Table(title="External Requirements")
    table.add_column("ID", no_wrap=True)
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Detected")
    table.add_column("Min")
    table.add_column("Hint", overflow="fold")

    bad = 0
    for r in results:
        style = _STATUS_STYLES.get(r.status, "white")
        if r.status not in (CheckStatus.OK,):
            bad += 1
        table.add_row(
            r.requirement.id,
            r.requirement.name,
            f"[{style}]{r.status.value}[/{style}]",
            r.detected_version or "-",
            r.requirement.min_version or "-",
            r.requirement.install_hint if r.status != CheckStatus.OK else "",
        )

    console.print(table)
    linger = systemd_linger_advisory()
    if linger:
        console.print(
            "[yellow]advisory (systemd-linger):[/yellow] "
            + linger
        )
    _print_install_channel_check()
    if bad:
        console.print(f"[red]{bad} requirement(s) need attention[/red]")
        raise typer.Exit(code=1)
    console.print("[green]all requirements satisfied[/green]")


@doctor_app.command(
    "render-requirements", help="Regenerate requirements.md (universal + per-runtime)."
)
def render_requirements() -> None:
    from llm_cli.core import registry as _registry
    from llm_cli.core.doctor import (
        render_requirements_md_grouped,
        requirements_for_runtime,
    )

    repo = scaffold_root()
    all_reqs = load_requirements(_requirements_yaml(repo))
    universal: list = []
    by_scope: dict[str, list] = {}
    for req in all_reqs:
        if req.scope:
            by_scope.setdefault(str(req.scope), []).append(req)
        else:
            universal.append(req)
    by_runtime: dict[str, list] = {}
    for mf in _registry.load_runtime_manifests_merged():
        reqs = requirements_for_runtime(repo, mf.id, build_params={})
        if reqs:
            by_runtime[mf.id] = reqs
    md = render_requirements_md_grouped(universal, by_runtime, by_scope=by_scope)
    out = repo / "requirements.md"
    out.write_text(md, encoding="utf-8")
    console.print(f"[green]wrote[/green] {out}")
