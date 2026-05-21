"""`loco update` — Typer wrapper around core.update_ops."""
from __future__ import annotations

import json
from dataclasses import asdict

import typer

from llm_cli.core import update_ops as ops
from llm_cli.core.update_ops import GitCommandError, UpdateError
from llm_cli.core.versions import check_for_update

console = ops.console


def update(
    branch: str | None = typer.Option(
        None,
        "--branch",
        help="Switch to the tip of the given branch (off-mainline; warns).",
    ),
    tag: str | None = typer.Option(
        None,
        "--tag",
        help="Pin to a specific tag (e.g. v0.4.0).",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Report current vs. latest tag and exit 1 if behind. No changes.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Machine-readable output (only with --check).",
    ),
    restart: bool = typer.Option(
        False,
        "--restart",
        help="Stop a running service before update and re-serve afterward.",
    ),
    stable: bool = typer.Option(
        False,
        "--stable",
        help="Switch to the latest release tag (leave feature branches).",
    ),
) -> None:
    """Refresh the install checkout: current branch/tag by default, or a chosen ref."""
    if json_output and not check:
        console.print("[red]error:[/red] --json is only valid with --check.")
        raise typer.Exit(code=1)
    if sum(bool(x) for x in (branch, tag, check, stable)) > 1:
        console.print(
            "[red]error:[/red] --branch, --tag, --check, and --stable are mutually exclusive."
        )
        raise typer.Exit(code=1)

    root = ops.scaffold_root()
    if not ops._is_git_clone(root):
        console.print(
            f"[red]error:[/red] {root} is not a managed install (no .git). "
            "Reinstall via the install.sh one-liner."
        )
        raise typer.Exit(code=1)
    if not ops._remote_matches_expected(root):
        console.print(
            f"[red]error:[/red] {root}/.git/config 'origin' does not look like "
            "github.com/mtopcu1/loco-llm. Refusing to update."
        )
        raise typer.Exit(code=1)

    try:
        ops._fetch_remote(root, refspec=branch)
    except GitCommandError as exc:
        ops._report_git_error(exc, action="fetch", branch=branch, tag=tag)
        raise typer.Exit(code=1) from None

    try:
        state = ops._current_state(root)
    except GitCommandError as exc:
        ops._report_git_error(exc, action="inspect", branch=branch, tag=tag)
        raise typer.Exit(code=1) from None

    if check:
        if json_output:
            info = check_for_update()
            typer.echo(json.dumps(asdict(info)))
            raise typer.Exit(code=0 if not info.update_available else 1)
        latest = ops._latest_tag(root)
        if latest is None:
            console.print("[yellow]warning:[/yellow] no semver tags on origin.")
            raise typer.Exit(code=0)
        console.print(f"  current: {state['ref'] or state['sha'][:7]}")
        console.print(f"  latest:  {latest}")
        if state["kind"] == "tag" and state["ref"] == latest:
            console.print("Already on latest stable.")
            raise typer.Exit(code=0)
        raise typer.Exit(code=1)

    if branch is not None:
        try:
            ops._update_branch_tip(root, branch, restart=restart)
        except GitCommandError as exc:
            ops._report_git_error(exc, action="update", branch=branch)
            raise typer.Exit(code=1) from None
        console.print(
            f"[yellow]you are on branch {branch} — not a stable release.[/yellow] "
            "Run `loco update --stable` to switch to the latest release tag."
        )
        return

    if tag is not None:
        try:
            ops._update_to_tag(root, tag, restart=restart)
        except GitCommandError as exc:
            ops._report_git_error(exc, action="update", tag=tag)
            raise typer.Exit(code=1) from None
        console.print(f"[green]pinned to {tag}.[/green]")
        return

    if stable:
        latest = ops._latest_tag(root)
        if latest is None:
            console.print(
                "[red]error:[/red] no semver tags on origin; cannot switch to stable. "
                "Use `--branch <name>` to track a branch instead."
            )
            raise typer.Exit(code=1)
        if state["kind"] == "tag" and state["ref"] == latest:
            try:
                saved = ops._apply_update(root, restart=restart)
                ops._finish_update(root, saved=saved)
            except GitCommandError as exc:
                ops._report_git_error(exc, action="update")
                raise typer.Exit(code=1) from None
            console.print(f"Already on latest stable ({latest}); dependencies synced.")
            return
        try:
            ops._update_to_tag(root, latest, restart=restart)
        except GitCommandError as exc:
            ops._report_git_error(exc, action="update")
            raise typer.Exit(code=1) from None
        if state["kind"] == "branch":
            console.print(
                f"[yellow]switched from branch {state['ref']} to latest stable {latest}.[/yellow]"
            )
        else:
            console.print(f"[green]updated to {latest}.[/green]")
        return

    if state["kind"] == "branch" and state["ref"]:
        try:
            ops._update_branch_tip(root, state["ref"], restart=restart)
        except GitCommandError as exc:
            ops._report_git_error(exc, action="update", branch=state["ref"])
            raise typer.Exit(code=1) from None
        console.print(f"[green]updated branch {state['ref']} to latest tip.[/green]")
        return

    if state["kind"] == "tag":
        latest = ops._latest_tag(root)
        if latest is None:
            console.print(
                "[red]error:[/red] no semver tags on origin. "
                "Use `--branch <name>` to track a branch."
            )
            raise typer.Exit(code=1)
        if state["ref"] == latest:
            try:
                saved = ops._apply_update(root, restart=restart)
                ops._finish_update(root, saved=saved)
            except GitCommandError as exc:
                ops._report_git_error(exc, action="update")
                raise typer.Exit(code=1) from None
            console.print(f"Already on latest stable ({latest}); dependencies synced.")
            return
        try:
            ops._update_to_tag(root, latest, restart=restart)
        except GitCommandError as exc:
            ops._report_git_error(exc, action="update")
            raise typer.Exit(code=1) from None
        console.print(f"[green]updated to {latest}.[/green]")
        return

    try:
        saved = ops._apply_update(root, restart=restart)
        ops._finish_update(root, saved=saved)
    except GitCommandError as exc:
        ops._report_git_error(exc, action="update")
        raise typer.Exit(code=1) from None
    console.print(
        f"[yellow]detached at {state['sha'][:7]}; dependencies synced only.[/yellow] "
        "Checkout a branch or tag, or use `--stable` / `--tag`."
    )
