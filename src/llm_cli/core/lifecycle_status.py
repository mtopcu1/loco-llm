"""Helpers to detect whether a lifecycle service is running."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.lifecycle import is_alive, read_running, reconcile
from llm_cli.core.settings import Settings
from llm_cli.core.systemd_unit import is_active as systemd_is_active


def service_is_running(state_base: Path) -> bool:
    """True if ``llm status`` would report an active service."""
    reconcile(state_base)
    rec = read_running(state_base)
    if rec is None:
        return False
    if rec.mode in ("foreground", "background"):
        return rec.pid is not None and is_alive(rec.pid)
    if rec.mode == "systemd":
        return bool(rec.unit) and systemd_is_active(rec.unit)
    return False


def service_is_running_for_settings(settings: Settings) -> bool:
    from llm_cli.core.lifecycle import state_root

    return service_is_running(state_root(settings))
