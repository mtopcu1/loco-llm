"""Build argv for `python -m llm_cli` subprocess invocations."""
from __future__ import annotations

import sys


def llm_cli_argv(*args: str) -> list[str]:
    return [sys.executable, "-m", "llm_cli", *args]
