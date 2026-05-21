"""Git checkout update logic (CLI and dashboard API)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

from rich.console import Console

from llm_cli.core.lifecycle import read_running, state_root, stop_instance
from llm_cli.core.lifecycle_status import service_is_running_for_settings
from llm_cli.core.serve import serve_dispatch
from llm_cli.core.scaffold import scaffold_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.versions import check_for_update, current_cli_version

console = Console()


class UpdateError(Exception):
    """Update failed with a user-visible message."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)

_SEMVER_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_EXPECTED_REMOTE_HOSTS = ("github.com/mtopcu1/loco-llm",)


class GitCommandError(RuntimeError):
    """Raised when a git subprocess exits non-zero."""

    def __init__(
        self,
        cmd: list[str],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(self.detail())

    def detail(self) -> str:
        return (self.stderr or self.stdout or "").strip()


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(root), *args]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise GitCommandError(
            cmd,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
    return completed


def _report_git_error(
    exc: GitCommandError,
    *,
    action: str,
    branch: str | None = None,
    tag: str | None = None,
) -> None:
    """Print a short, actionable message instead of a Python traceback."""
    console.print(f"[red]error:[/red] git {action} failed (exit {exc.returncode}).")
    detail = exc.detail()
    if detail:
        for line in detail.splitlines():
            console.print(f"  {line}")
    lowered = detail.lower()
    if branch is not None:
        if (
            "couldn't find remote ref" in lowered
            or "not found in upstream origin" in lowered
            or "invalid refspec" in lowered
            or exc.returncode == 128
        ):
            console.print(
                f"[yellow]hint:[/yellow] branch {branch!r} is not on origin yet. "
                f"Push it from your dev machine, then retry:\n"
                f"  git push -u origin {branch}\n"
                f"  loco update --branch {branch}"
            )
        else:
            console.print(
                f"[dim]While updating to branch {branch!r}. "
                "Check network access and `git remote -v` in the install root.[/dim]"
            )
    elif tag is not None:
        console.print(
            f"[yellow]hint:[/yellow] tag {tag!r} may not exist on origin "
            "(run `git fetch --tags` locally to verify)."
        )


def _is_git_clone(root: Path) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        _run_git(root, "rev-parse", "--is-inside-work-tree")
    except GitCommandError:
        return False
    return True


def _remote_matches_expected(root: Path) -> bool:
    try:
        out = _run_git(root, "remote", "get-url", "origin")
    except GitCommandError:
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
    except GitCommandError:
        pass
    return {"kind": "detached", "ref": None, "sha": sha}


def _working_tree_dirty(root: Path) -> bool:
    out = _run_git(root, "status", "--porcelain")
    return bool(out.stdout.strip())


def _checkout(root: Path, ref: str) -> None:
    _run_git(root, "checkout", ref)


def _checkout_branch(root: Path, branch: str) -> None:
    """Check out a branch, creating a local branch from origin/<branch> if needed."""
    local = _run_git(
        root,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        check=False,
    )
    if local.returncode == 0:
        _run_git(root, "checkout", branch)
        return
    remote = _run_git(
        root,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/remotes/origin/{branch}",
        check=False,
    )
    if remote.returncode == 0:
        _run_git(root, "checkout", "-B", branch, f"origin/{branch}")
        return
    raise GitCommandError(
        ["git", "-C", str(root), "checkout", branch],
        1,
        "",
        f"branch {branch!r} not found locally or as origin/{branch}",
    )


def _ff_pull(root: Path, branch: str) -> None:
    _run_git(root, "pull", "--ff-only", "origin", branch)


def _venv_python(root: Path) -> Path | None:
    """Return the managed venv interpreter, matching scripts/install.sh layout."""
    candidate = root / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


def _sync_deps(root: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        console.print(
            "[yellow]warning:[/yellow] `uv` not found on PATH; skipping dep sync. "
            "Install uv and re-run `loco update` to pick up dependency changes."
        )
        return
    venv_python = _venv_python(root)
    if venv_python is None:
        console.print(
            f"[red]error:[/red] no venv at {root / '.venv'}; "
            "re-run the install.sh one-liner to recreate the managed environment."
        )
        raise UpdateError(
            f"no venv at {root / '.venv'}; "
            "re-run the install.sh one-liner to recreate the managed environment."
        )
    subprocess.run(
        [uv, "pip", "install", "--python", str(venv_python), "-e", str(root)],
        check=True,
    )


def _service_running() -> bool:
    settings = resolve(load_settings())
    return service_is_running_for_settings(settings)


def _maybe_restart_around_update(restart: bool):
    """Context-manager-ish helper returning (saved_record_or_none)."""
    if not _service_running():
        return None
    if not restart:
        raise UpdateError(
            "a service is running. Stop it first (`loco stop`) "
            "or pass --restart to stop and re-start it around the update."
        )
    settings = resolve(load_settings())
    saved = read_running(state_root(settings))
    stop_instance(strict_systemd=False)
    return saved


def _restore_service(saved) -> None:
    if saved is None:
        return
    serve_dispatch(
        saved.config_id,
        foreground=saved.mode == "foreground",
        systemd=saved.mode == "systemd",
    )


def _apply_update(
    root: Path,
    *,
    restart: bool,
    fetch_refspec: str | None = None,
) -> object | None:
    """Stash if needed, update checkout, sync deps, restore service. Returns saved record."""
    saved = _maybe_restart_around_update(restart)
    if _working_tree_dirty(root):
        _run_git(root, "stash", "push", "-u", "-m", "llm-update")
        console.print("[yellow]stashed local changes[/yellow]")
    if fetch_refspec:
        _fetch_remote(root, refspec=fetch_refspec)
    return saved


def _finish_update(root: Path, *, saved) -> None:
    _sync_deps(root)
    _restore_service(saved)
    _post_update_hooks()


def _update_branch_tip(root: Path, branch: str, *, restart: bool) -> None:
    saved = _apply_update(root, restart=restart, fetch_refspec=branch)
    _checkout_branch(root, branch)
    _ff_pull(root, branch)
    _finish_update(root, saved=saved)


def _update_to_tag(root: Path, tag: str, *, restart: bool) -> None:
    saved = _apply_update(root, restart=restart)
    _checkout(root, tag)
    _finish_update(root, saved=saved)


def _post_update_hooks() -> None:
    """Run best-effort post-update hooks."""
    from llm_cli.core import dashboard as dash

    try:
        record = dash.load_installed_record()
    except RuntimeError:
        return
    if record is None:
        return

    cli_version = current_cli_version()
    if record.cli_version == cli_version:
        return
    if not shutil.which("node") or not shutil.which("npm"):
        console.print(
            "[yellow]warning:[/yellow] dashboard is installed but node/npm not found; "
            "skipping rebuild. Run `loco dashboard install` after installing Node 20+."
        )
        return

    try:
        dash.run_install(
            cli_version=cli_version,
            skip_python=False,
            skip_frontend=False,
            reset=False,
        )
        console.print("[green]dashboard rebuilt to match updated CLI version.[/green]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]warning:[/yellow] dashboard rebuild failed: {exc}")


def run_default_update(*, restart: bool) -> None:
    """Refresh the current checkout (same default path as bare ``loco update``)."""
    root = scaffold_root()
    if not _is_git_clone(root):
        raise UpdateError(
            f"{root} is not a managed install (no .git). "
            "Reinstall via the install.sh one-liner."
        )
    if not _remote_matches_expected(root):
        raise UpdateError(
            f"{root}/.git/config 'origin' does not look like "
            "github.com/mtopcu1/loco-llm. Refusing to update."
        )
    _fetch_remote(root, refspec=None)
    state = _current_state(root)

    if state["kind"] == "branch" and state["ref"]:
        _update_branch_tip(root, state["ref"], restart=restart)
        return

    if state["kind"] == "tag":
        latest = _latest_tag(root)
        if latest is None:
            raise UpdateError(
                "no semver tags on origin. Use `--branch <name>` to track a branch."
            )
        if state["ref"] == latest:
            saved = _apply_update(root, restart=restart)
            _finish_update(root, saved=saved)
            return
        _update_to_tag(root, latest, restart=restart)
        return

    saved = _apply_update(root, restart=restart)
    _finish_update(root, saved=saved)
