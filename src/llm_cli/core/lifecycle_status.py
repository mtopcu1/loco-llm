"""Helpers to detect whether a lifecycle service is running."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_cli.core import registry
from llm_cli.core.lifecycle import is_alive, read_running, reconcile, state_root
from llm_cli.core.settings import Settings, resolve_settings
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
    return service_is_running(state_root(settings))


def current() -> dict[str, Any]:
    """Snapshot of the running instance for dashboard metrics and SSE."""
    settings = resolve_settings()
    root = state_root(settings)
    reconcile(root)
    rec = read_running(root)
    if rec is None:
        return {"running": False}
    cfg = registry.get_config_merged(rec.config_id)
    runtime_id: str | None = None
    if cfg and isinstance(cfg.data.get("runtime"), str):
        runtime_id = cfg.data["runtime"]
    return {
        "running": True,
        "config_id": rec.config_id,
        "runtime_id": runtime_id,
        "port": rec.port,
        "mode": rec.mode,
    }
