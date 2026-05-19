"""`llm update` — upgrade CLI wheel and scaffold assets."""
from __future__ import annotations

import shutil
import subprocess
import sys
import typer
from rich.console import Console

from llm_cli import __version__
from llm_cli.commands import lifecycle_cmds
from llm_cli.commands import serve as serve_cmd
from llm_cli.core.doctor import run_quick_checks
from llm_cli.core.lifecycle import read_running, state_root
from llm_cli.core.lifecycle_status import service_is_running_for_settings
from llm_cli.core.scaffold import configured_repo_root, read_scaffold_version
from llm_cli.core.scaffold_update import (
    install_scaffold_release,
    remove_scaffold_backup,
    rollback_scaffold,
)
from llm_cli.core.update_check import (
    fetch_github_latest_release,
    fetch_pypi_latest_version,
    is_behind,
    parse_version_tag,
)

console = Console()

_GITHUB_RELEASE_URL = "https://github.com/mtopcu1/local-llm-scaffold/releases/tag/"


def _pipx_available() -> bool:
    return shutil.which("pipx") is not None


def _upgrade_cli_wheel() -> None:
    if configured_repo_root() is not None:
        console.print(
            "[red]error:[/red] editable dev install detected; "
            "use `git pull` in your checkout instead of upgrading the CLI."
        )
        raise typer.Exit(code=1)
    if _pipx_available():
        subprocess.run(
            [
                "pipx",
                "upgrade",
                "localllm-cli",
                "--pip-args=--upgrade-strategy=eager",
            ],
            check=True,
        )
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "localllm-cli"],
        check=True,
    )


def _print_changelog(release: dict, tag: str) -> None:
    body = (release.get("body") or "").strip()
    console.print("\n[bold]Changelog highlights:[/bold]")
    if body:
        for line in body.splitlines()[:8]:
            console.print(f"  {line}")
        if len(body.splitlines()) > 8:
            console.print("  ...")
    console.print(f"  Full release: {_GITHUB_RELEASE_URL}{tag}")


def _confirm(yes: bool) -> None:
    if yes:
        return
    answer = typer.confirm("Continue?", default=True)
    if not answer:
        raise typer.Exit(code=0)


def _reexec_version() -> str:
    """Best-effort read of installed CLI version after pipx upgrade."""
    from importlib.metadata import version as pkg_version

    try:
        return pkg_version("localllm-cli")
    except Exception:  # noqa: BLE001
        return __version__


def update(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
    check: bool = typer.Option(
        False, "--check", help="Report available versions; exit 1 if behind."
    ),
    scaffold_only: bool = typer.Option(
        False, "--scaffold-only", help="Update scaffold assets only."
    ),
    cli_only: bool = typer.Option(False, "--cli-only", help="Update CLI wheel only."),
    restart: bool = typer.Option(
        False,
        "--restart",
        help="Stop a running service before update and re-serve afterward.",
    ),
) -> None:
    """Upgrade CLI and/or scaffold assets from PyPI and GitHub releases."""
    if scaffold_only and cli_only:
        console.print("[red]error:[/red] --scaffold-only and --cli-only are mutually exclusive.")
        raise typer.Exit(code=1)

    from llm_cli.core.settings import load_settings, resolve

    settings = resolve(load_settings())
    cli_current = __version__
    scaffold_current = read_scaffold_version()
    scaffold_current_cmp = (
        parse_version_tag(scaffold_current) if scaffold_current else None
    )

    console.print("Checking for updates...")
    try:
        pypi_latest = fetch_pypi_latest_version()
        release = fetch_github_latest_release()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]error:[/red] failed to check for updates: {exc}")
        raise typer.Exit(code=1) from exc

    tag = str(release.get("tag_name", ""))
    if not tag:
        console.print("[red]error:[/red] GitHub release missing tag_name")
        raise typer.Exit(code=1)
    scaffold_latest_cmp = parse_version_tag(tag)

    cli_behind = is_behind(cli_current, pypi_latest)
    scaffold_behind = (
        scaffold_current_cmp is None
        or is_behind(scaffold_current_cmp, scaffold_latest_cmp)
    )

    console.print(f"  CLI:      {cli_current}  →  {pypi_latest}  (PyPI)")
    console.print(
        f"  Scaffold: {scaffold_current or '(none)'}  →  {tag}  "
        "(github.com/mtopcu1/local-llm-scaffold)"
    )

    if check:
        if cli_behind or scaffold_behind:
            raise typer.Exit(code=1)
        console.print("Already up to date.")
        raise typer.Exit(code=0)

    need_cli = cli_behind and not scaffold_only
    need_scaffold = scaffold_behind and not cli_only
    if not need_cli and not need_scaffold:
        console.print("Already up to date.")
        raise typer.Exit(code=0)

    running = service_is_running_for_settings(settings)
    if running and not restart:
        console.print(
            "[red]error:[/red] Stop the running service first (`llm stop`), "
            "or pass --restart to have update stop and re-start it."
        )
        raise typer.Exit(code=1)

    saved_rec = None
    if running and restart:
        saved_rec = read_running(state_root(settings))
        lifecycle_cmds.stop()

    if need_cli or need_scaffold:
        _print_changelog(release, tag)
        _confirm(yes)

    prev_cli = cli_current
    did_cli = False
    did_scaffold = False

    if need_cli:
        console.print("[bold]Upgrading CLI...[/bold]")
        try:
            _upgrade_cli_wheel()
            did_cli = True
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]error:[/red] CLI upgrade failed: {exc}")
            raise typer.Exit(code=1) from exc

    if need_scaffold:
        console.print("[bold]Upgrading scaffold...[/bold]")
        try:
            install_scaffold_release(tag, list(release.get("assets") or []), yes=yes)
            did_scaffold = True
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]error:[/red] scaffold update failed: {exc}")
            raise typer.Exit(code=1) from exc

    if did_scaffold:
        new_cli = _reexec_version() if did_cli else cli_current
        if did_cli and new_cli != pypi_latest:
            console.print(
                f"[yellow]warning:[/yellow] CLI reports {new_cli} "
                f"(expected {pypi_latest}); re-open your shell if needed."
            )
        ok, detail = run_quick_checks()
        if not ok:
            console.print(f"[red]error:[/red] post-update verify failed: {detail}")
            rollback_scaffold()
            console.print("[yellow]warning:[/yellow] scaffold rolled back to previous version.")
            if did_cli:
                console.print(
                    f"CLI was upgraded to {pypi_latest}. "
                    f"To roll back: pipx install 'localllm-cli=={prev_cli}' --force"
                )
            raise typer.Exit(code=1)
        remove_scaffold_backup()

    if running and restart and saved_rec is not None:
        serve_cmd.serve_dispatch(
            saved_rec.config_id,
            foreground=saved_rec.mode == "foreground",
            systemd=saved_rec.mode == "systemd",
        )

    if did_cli and did_scaffold:
        console.print(f"[green]Updated to {pypi_latest} ({tag}).[/green]")
    elif did_cli:
        console.print(f"[green]Updated CLI to {pypi_latest}.[/green]")
    elif did_scaffold:
        console.print(f"[green]Updated scaffold to {tag}.[/green]")
