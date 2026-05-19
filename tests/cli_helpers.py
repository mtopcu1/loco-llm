"""Helpers for asserting on Typer/Rich CLI output in tests."""
from __future__ import annotations

from typer.testing import Result

from tests.tui.session import strip_ansi


def cli_plain(result: Result) -> str:
    """Plain text from CliRunner output (stdout, stderr, combined)."""
    parts = [result.output, result.stdout, result.stderr]
    return strip_ansi("".join(parts))
