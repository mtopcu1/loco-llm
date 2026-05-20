"""Lightweight version parsing and comparison.

Avoids depending on `packaging` for a tiny subset of needs.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
import re

_NUM_RE = re.compile(r"\d+")


def parse_version(raw: str) -> tuple[int, ...]:
    """Extract numeric components from a version-like string.

    Strips leading 'v' and any non-numeric suffix (e.g. '-rc1').
    Raises ValueError if no numeric components found.
    """
    text = raw.strip().lstrip("v")
    if "-" in text:
        text = text.split("-", 1)[0]
    parts = _NUM_RE.findall(text)
    if not parts:
        raise ValueError(f"no numeric components in version string: {raw!r}")
    return tuple(int(p) for p in parts)


def compare_versions(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b.

    Missing components are treated as 0, so '3.11' == '3.11.0'.
    """
    pa = parse_version(a)
    pb = parse_version(b)
    length = max(len(pa), len(pb))
    pa_padded = pa + (0,) * (length - len(pa))
    pb_padded = pb + (0,) * (length - len(pb))
    if pa_padded < pb_padded:
        return -1
    if pa_padded > pb_padded:
        return 1
    return 0


def current_cli_version() -> str:
    """Return the installed CLI package version."""
    try:
        return version("loco-llm-cli")
    except PackageNotFoundError:
        from llm_cli import __version__

        return __version__
