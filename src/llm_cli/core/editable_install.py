"""Detect broken pip editable installs (e.g. after deleting a git worktree)."""
from __future__ import annotations

import json
import sysconfig
from pathlib import Path
from urllib.parse import unquote, urlparse

_DIST_NAME = "loco-llm-cli"


def _windows_file_url_path(url: str) -> Path:
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if (
        len(path) >= 3
        and path[0] == "/"
        and path[2] == ":"
        and path[1].isalpha()
    ):
        return Path(path[1:])
    return Path(path)


def editable_project_path() -> Path | None:
    """Return the editable checkout path from direct_url.json, or None if not editable."""
    for base in (
        Path(sysconfig.get_path("purelib")),
        Path(sysconfig.get_path("platlib")),
    ):
        for meta in base.glob("loco_llm_cli*.dist-info"):
            direct = meta / "direct_url.json"
            if not direct.is_file():
                continue
            try:
                data = json.loads(direct.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not data.get("dir_info", {}).get("editable"):
                continue
            url = data.get("url", "")
            if not url.startswith("file:"):
                continue
            return _windows_file_url_path(url)
    return None


def check_editable_install() -> tuple[str, str, str]:
    """Return (check_id, status, message) for doctor-style reporting."""
    path = editable_project_path()
    if path is None:
        return ("cli-editable", "info", "CLI not installed as pip editable (or direct_url missing)")
    if path.is_dir():
        return ("cli-editable", "ok", f"Editable install points at {path}")
    return (
        "cli-editable",
        "error",
        f"Editable install target missing: {path}. "
        "Reinstall from your checkout: pip install -e \".[dev]\"",
    )
