"""`llm update` — pull the latest tag (or a chosen ref) into the git checkout."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.commands import lifecycle_cmds
from llm_cli.commands import serve as serve_cmd
from llm_cli.core.lifecycle import read_running, state_root
from llm_cli.core.lifecycle_status import service_is_running_for_settings
from llm_cli.core.scaffold import scaffold_root
from llm_cli.core.settings import load_settings, resolve

console = Console()

_SEMVER_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_EXPECTED_REMOTE_HOSTS = ("github.com/mtopcu1/loco-llm",)


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _is_git_clone(root: Path) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        _run_git(root, "rev-parse", "--is-inside-work-tree")
    except subprocess.CalledProcessError:
        return False
    return True


def _remote_matches_expected(root: Path) -> bool:
    try:
        out = _run_git(root, "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        return False
    url = out.stdout.strip()
    return any(host in url for host in _EXPECTED_REMOTE_HOSTS)


def _fetch_remote(root: Path, refspec: str | None = None) -> None:
    args = ["fetch", "--tags", "--prune", "origin"]
    if refspec:
        args.append(refspec)
    _run_git(root, *args)


def _list_semver_tags(root: Path) -> list[str]:
    out = _run_git(root, "tag", "--list", "v*")
    tags = [t for t in out.stdout.split() if _SEMVER_TAG.match(t)]

    def key(tag: str) -> tuple[int, int, int]:
        parts = tag[1:].split(".")
        return tuple(int(p) for p in parts)  # type: ignore[return-value]

    return sorted(tags, key=key)


def _latest_tag(root: Path) -> str | None:
    tags = _list_semver_tags(root)
    return tags[-1] if tags else None


def _current_state(root: Path) -> dict[str, str | None]:
    """Return {kind, ref, sha} where kind is 'tag' | 'branch' | 'detached'."""
    sha = _run_git(root, "rev-parse", "HEAD").stdout.strip()
    branch = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch and branch != "HEAD":
        return {"kind": "branch", "ref": branch, "sha": sha}
    try:
        tag = _run_git(root, "describe", "--tags", "--exact-match", "HEAD").stdout.strip()
        if tag:
            return {"kind": "tag", "ref": tag, "sha": sha}
    except subprocess.CalledProcessError:
        pass
    return {"kind": "detached", "ref": None, "sha": sha}


def _working_tree_dirty(root: Path) -> bool:
    out = _run_git(root, "status", "--porcelain")
    return bool(out.stdout.strip())


def _checkout(root: Path, ref: str) -> None:
    _run_git(root, "checkout", ref)


def _ff_pull(root: Path, branch: str) -> None:
    _run_git(root, "pull", "--ff-only", "origin", branch)


def _sync_deps(root: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        console.print(
            "[yellow]warning:[/yellow] `uv` not found on PATH; skipping dep sync. "
            "Install uv and re-run `llm update` to pick up dependency changes."
        )
        return
    subprocess.run([uv, "pip", "install", "-e", str(root)], check=True)


def _service_running() -> bool:
    settings = resolve(load_settings())
    return service_is_running_for_settings(settings)


def _maybe_restart_around_update(restart: bool):
    """Context-manager-ish helper returning (saved_record_or_none)."""
    if not _service_running():
        return None
    if not restart:
        console.print(
            "[red]error:[/red] a service is running. Stop it first (`llm stop`) "
            "or pass --restart to stop and re-start it around the update."
        )
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    saved = read_running(state_root(settings))
    lifecycle_cmds.stop()
    return saved


def _restore_service(saved) -> None:
    if saved is None:
        return
    serve_cmd.serve_dispatch(
        saved.config_id,
        foreground=saved.mode == "foreground",
        systemd=saved.mode == "systemd",
    )


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
    restart: bool = typer.Option(
        False,
        "--restart",
        help="Stop a running service before update and re-serve afterward.",
    ),
) -> None:
    """Pull the latest tagged release (or a chosen ref) into the local checkout."""
    if sum(bool(x) for x in (branch, tag, check)) > 1:
        console.print(
            "[red]error:[/red] --branch, --tag, and --check are mutually exclusive."
        )
        raise typer.Exit(code=1)

    root = scaffold_root()
    if not _is_git_clone(root):
        console.print(
            f"[red]error:[/red] {root} is not a managed install (no .git). "
            "Reinstall via the install.sh one-liner."
        )
        raise typer.Exit(code=1)
    if not _remote_matches_expected(root):
        console.print(
            f"[red]error:[/red] {root}/.git/config 'origin' does not look like "
            "github.com/mtopcu1/loco-llm. Refusing to update."
        )
        raise typer.Exit(code=1)

    _fetch_remote(root, refspec=branch)

    state = _current_state(root)

    if check:
        latest = _latest_tag(root)
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
        saved = _maybe_restart_around_update(restart)
        if _working_tree_dirty(root):
            _run_git(root, "stash", "push", "-u", "-m", "llm-update")
            console.print("[yellow]stashed local changes[/yellow]")
        _checkout(root, branch)
        _ff_pull(root, branch)
        _sync_deps(root)
        _restore_service(saved)
        console.print(
            f"[yellow]you are now on branch {branch} — not a stable release.[/yellow] "
            "Run `llm update` to return to the latest stable tag."
        )
        return

    if tag is not None:
        saved = _maybe_restart_around_update(restart)
        if _working_tree_dirty(root):
            _run_git(root, "stash", "push", "-u", "-m", "llm-update")
            console.print("[yellow]stashed local changes[/yellow]")
        _checkout(root, tag)
        _sync_deps(root)
        _restore_service(saved)
        console.print(f"[green]pinned to {tag}.[/green]")
        return

    latest = _latest_tag(root)
    if latest is None:
        console.print(
            "[red]error:[/red] no semver tags on origin; cannot re-anchor. "
            "Use `--branch main` if you intend to track an untagged branch."
        )
        raise typer.Exit(code=1)

    if state["kind"] == "branch":
        console.print(
            f"[yellow]currently on branch {state['ref']}; "
            f"switching back to latest stable tag {latest}.[/yellow]"
        )
    if state["kind"] == "tag" and state["ref"] == latest:
        console.print(f"Already on latest stable ({latest}).")
        return

    saved = _maybe_restart_around_update(restart)
    if _working_tree_dirty(root):
        _run_git(root, "stash", "push", "-u", "-m", "llm-update")
        console.print("[yellow]stashed local changes[/yellow]")
    _checkout(root, latest)
    _sync_deps(root)
    _restore_service(saved)
    console.print(f"[green]updated to {latest}.[/green]")
