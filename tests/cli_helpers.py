"""Helpers for asserting on Typer/Rich CLI output in tests."""
from __future__ import annotations

from typer.testing import Result

from tests.tui.session import strip_ansi


def cli_plain(result: Result) -> str:
    """Plain text from CliRunner output (stdout, stderr, combined)."""
    parts = [result.output, result.stdout, result.stderr]
    return strip_ansi("".join(parts))


def data_root_path(tmp_path: Path) -> Path:
    """Hermes layout data home used by integration tests."""
    return tmp_path / "data"


def data_config_path(tmp_path: Path, name: str) -> Path:
    """Path to a launch config under {data_root}/configs/."""
    return data_root_path(tmp_path) / "configs" / name
