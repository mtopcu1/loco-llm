"""Install-channel checks used by ``loco doctor`` and setup flows."""
from __future__ import annotations

import subprocess
from pathlib import Path

from llm_cli.core.scaffold import scaffold_root as install_root


def check_on_release_tag() -> tuple[str, str, str]:
    """Return (id, status, detail) for the head-on-tag check."""
    try:
        root = install_root()
    except RuntimeError as exc:
        return ("install-channel", "error", str(exc))
    try:
        subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True,
            check=True,
            timeout=2,
        )
        return ("install-channel", "ok", "on a release tag")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return (
            "install-channel",
            "warn",
            "not on a release tag — run `loco update --stable` for the latest release tag",
        )
