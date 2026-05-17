"""`llm doctor` — verify external requirements; `llm doctor render-requirements` regenerates the markdown."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.doctor import (
    CheckStatus,
    check_all,
    load_requirements,
    systemd_linger_advisory,
)
from llm_cli.core.repo import repo_root

console = Console()
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
) -> None:
    """Run requirement checks: universal + runtime-scoped extras."""
    if ctx.invoked_subcommand is not None:
        return

    repo = repo_root()
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

        mf = _registry.get_runtime_manifest(repo, runtime)
        if mf is None:
            console.print(f"[red]error:[/red] unknown runtime {runtime!r}")
            raise typer.Exit(code=1)

        rec = read_record(settings.runtimes_dir, runtime)
        build_params = (
            dict(rec.build_params)
            if rec is not None
            else {
                spec.key: spec.default
                for spec in mf.build_schema
                if spec.default is not None
            }
        )
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

    repo = repo_root()
    universal = load_requirements(_requirements_yaml(repo))
    by_runtime: dict[str, list] = {}
    for mf in _registry.load_runtime_manifests(repo):
        defaults = {spec.key: spec.default for spec in mf.build_schema if spec.default is not None}
        reqs = requirements_for_runtime(repo, mf.id, build_params=defaults)
        if reqs:
            by_runtime[mf.id] = reqs
    md = render_requirements_md_grouped(universal, by_runtime)
    out = repo / "requirements.md"
    out.write_text(md, encoding="utf-8")
    console.print(f"[green]wrote[/green] {out}")
