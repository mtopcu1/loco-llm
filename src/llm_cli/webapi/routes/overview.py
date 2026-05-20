from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from llm_cli.core import dashboard, disk, doctor, install_record, lifecycle, model_registry, registry
from llm_cli.core.settings import resolve_settings
from llm_cli.core.versions import current_cli_version

router = APIRouter()


@router.get("/overview", tags=["overview"])
def get_overview():
    settings = resolve_settings()
    state_root = lifecycle.state_root(settings)

    try:
        dashboard_record = dashboard.load_installed_record()
    except RuntimeError:
        dashboard_record = None

    running = lifecycle.read_running(state_root)
    instance = {"running": False} if running is None else {"running": True, **asdict(running)}

    runtimes = registry.load_runtime_manifests_merged()
    installed_count = sum(
        1 for runtime in runtimes if install_record.read_record(settings.runtimes_dir, runtime.id) is not None
    )
    models = model_registry.load_registry(settings.models_dir)
    configs = registry.discover_configs_merged()

    doctor_summary: dict[str, dict[str, int]] = {}
    for scope in ("default", "runtime", "dashboard"):
        checks = doctor.run_scope(scope)
        summary = {"error": 0, "warning": 0, "ok": 0}
        for check in checks:
            status = str(check.status)
            if status in summary:
                summary[status] += 1
        doctor_summary[scope] = summary

    history = lifecycle.read_history(state_root)
    recent_history = history[-5:]

    disk_report = disk.scan()
    pct_used = 0.0
    if disk_report.data_root_bytes_total:
        pct_used = (disk_report.data_root_bytes_used / disk_report.data_root_bytes_total) * 100.0

    return {
        "version": {
            "cli_version": current_cli_version(),
            "dashboard_installed_cli_version": dashboard_record.cli_version if dashboard_record else None,
            "dashboard_installed_at": dashboard_record.installed_at if dashboard_record else None,
        },
        "instance": instance,
        "runtimes_count": len(runtimes),
        "runtimes_installed_count": installed_count,
        "models_count": len(models),
        "configs_count": len(configs),
        "doctor_summary": doctor_summary,
        "recent_history": recent_history,
        "disk_summary": {
            "data_root_pct_used": pct_used,
            "models_count": len(disk_report.models),
            "cache_bytes": disk_report.cache_bytes,
        },
    }
