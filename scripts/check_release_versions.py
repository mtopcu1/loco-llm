#!/usr/bin/env python3
"""Assert pyproject.toml, __init__.py, and release-please manifest agree."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("pyproject.toml: missing version field")
    return match.group(1)


def _init_version() -> str:
    text = (ROOT / "src" / "llm_cli" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', text)
    if not match:
        raise SystemExit("src/llm_cli/__init__.py: missing __version__")
    return match.group(1)


def _manifest_version() -> str:
    data = json.loads(
        (ROOT / ".release-please-manifest.json").read_text(encoding="utf-8")
    )
    if "." not in data:
        raise SystemExit(".release-please-manifest.json: missing '.' entry")
    return str(data["."])


def main() -> None:
    pyproject = _pyproject_version()
    init = _init_version()
    manifest = _manifest_version()
    if pyproject == init == manifest:
        print(f"version sync ok: {pyproject}")
        return
    print(
        "version mismatch:\n"
        f"  pyproject.toml: {pyproject}\n"
        f"  __init__.py:    {init}\n"
        f"  manifest:       {manifest}",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
