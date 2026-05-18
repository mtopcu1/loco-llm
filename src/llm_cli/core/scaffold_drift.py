"""Passive CLI vs scaffold version drift detection (spec §9.4)."""
from __future__ import annotations

import sys
from enum import Enum

import typer

from llm_cli import __version__
from llm_cli.core.scaffold import configured_repo_root, read_scaffold_version
from llm_cli.core.update_check import parse_version_tag
from llm_cli.core.versions import parse_version

_warned_this_process = False


class DriftSeverity(str, Enum):
    OK = "ok"
    MISSING = "missing"
    PATCH = "patch"
    MINOR_OR_MAJOR = "minor_or_major"


def classify_drift(cli_version: str, scaffold_tag: str | None) -> DriftSeverity:
    if scaffold_tag is None:
        return DriftSeverity.MISSING
    cli_parts = parse_version(cli_version)
    sc_parts = parse_version(parse_version_tag(scaffold_tag))
    if cli_parts[:2] != sc_parts[:2]:
        return DriftSeverity.MINOR_OR_MAJOR
    if cli_parts != sc_parts:
        return DriftSeverity.PATCH
    return DriftSeverity.OK


def _is_destructive_invocation() -> bool:
    argv = sys.argv[1:]
    if not argv:
        return False
    if argv[0] == "serve":
        return True
    if len(argv) >= 2 and argv[0] == "runtime" and argv[1] == "install":
        return True
    if len(argv) >= 2 and argv[0] == "model" and argv[1] == "pull":
        return True
    return False


def _command_is_update() -> bool:
    argv = sys.argv[1:]
    return bool(argv) and argv[0] == "update"


def check_scaffold_drift() -> None:
    """Print drift warnings or refuse destructive commands."""
    global _warned_this_process  # noqa: PLW0603

    if _command_is_update():
        return
    if configured_repo_root() is not None:
        return

    scaffold_tag = read_scaffold_version()
    severity = classify_drift(__version__, scaffold_tag)

    if severity == DriftSeverity.OK:
        return

    destructive = _is_destructive_invocation()

    if severity in (DriftSeverity.MISSING, DriftSeverity.MINOR_OR_MAJOR):
        msg = (
            "scaffold version drift — run `llm update --scaffold-only`"
            if severity == DriftSeverity.MINOR_OR_MAJOR
            else "missing .scaffold-version — run `llm update --scaffold-only`"
        )
        if destructive:
            typer.secho(f"error: {msg}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        if not _warned_this_process:
            typer.secho(f"warning: {msg}", fg=typer.colors.YELLOW, err=True)
            _warned_this_process = True
        return

    # Patch-level mismatch
    if not _warned_this_process:
        cli_v = __version__
        sc_v = parse_version_tag(scaffold_tag or "")
        typer.secho(
            f"warning: CLI ({cli_v}) and scaffold (v{sc_v}) versions differ slightly; "
            "run `llm update` to align.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        _warned_this_process = True
