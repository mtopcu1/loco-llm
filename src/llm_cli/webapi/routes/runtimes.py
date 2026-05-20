from __future__ import annotations

import sys
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from llm_cli.core import install_record, jobs as jobs_module, registry
from llm_cli.core.lifecycle import read_running, reconcile, state_root
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


def _llm_argv(*args: str) -> list[str]:
    return [sys.executable, "-m", "llm_cli", *args]


def _running_runtime_id() -> tuple[str | None, str | None]:
    """Return (runtime_id, config_id) when a service is running, else (None, None)."""
    settings = resolve_settings()
    root = state_root(settings)
    reconcile(root)
    rec = read_running(root)
    if rec is None:
        return None, None
    cfg = registry.get_config_merged(rec.config_id)
    if cfg is None:
        return None, rec.config_id
    rt = cfg.data.get("runtime")
    return (str(rt) if isinstance(rt, str) else None), rec.config_id


class RuntimeSummary(BaseModel):
    id: str
    kind: str
    installed: bool
    installed_at: str | None
    has_metrics: bool


class RuntimeDetail(BaseModel):
    id: str
    kind: str
    manifest: dict[str, Any]
    installed: bool
    install_record: dict[str, Any] | None
    drift: dict[str, Any] | None


@router.get("/runtimes", response_model=list[RuntimeSummary], tags=["runtimes"])
def list_runtimes():
    settings = resolve_settings()
    out: list[RuntimeSummary] = []
    for rt in registry.load_runtime_manifests_merged():
        rec = install_record.read_record(settings.runtimes_dir, rt.id)
        out.append(
            RuntimeSummary(
                id=rt.id,
                kind=rt.kind,
                installed=rec is not None,
                installed_at=rec.installed_at if rec else None,
                has_metrics=False,
            )
        )
    return out


@router.get("/runtimes/{runtime_id}", response_model=RuntimeDetail, tags=["runtimes"])
def get_runtime(runtime_id: str):
    runtime_record = registry.get_runtime_merged(runtime_id)
    if runtime_record is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )

    runtime_manifest = registry.get_runtime_manifest_merged(runtime_id)
    if runtime_manifest is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )

    settings = resolve_settings()
    rec = install_record.read_record(settings.runtimes_dir, runtime_id)
    return RuntimeDetail(
        id=runtime_manifest.id,
        kind=runtime_manifest.kind,
        manifest=runtime_record.manifest,
        installed=rec is not None,
        install_record=asdict(rec) if rec else None,
        drift=None,
    )


@router.post("/runtimes/{runtime_id}/install", tags=["runtimes"])
def install_runtime_route(runtime_id: str):
    if registry.get_runtime_merged(runtime_id) is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )
    job_id = jobs_module.registry().start_subprocess(
        kind="runtime_install",
        context={"runtime_id": runtime_id},
        argv=_llm_argv("runtime", "install", runtime_id, "--yes"),
    )
    return {"job_id": job_id}


@router.post("/runtimes/{runtime_id}/rebuild", tags=["runtimes"])
def rebuild_runtime_route(runtime_id: str, reset: bool = Query(default=False)):
    if registry.get_runtime_merged(runtime_id) is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )
    argv = _llm_argv("runtime", "rebuild", runtime_id, "--yes")
    if reset:
        argv.append("--reset")
    job_id = jobs_module.registry().start_subprocess(
        kind="runtime_rebuild",
        context={"runtime_id": runtime_id, "reset": reset},
        argv=argv,
    )
    return {"job_id": job_id}


@router.delete("/runtimes/{runtime_id}", tags=["runtimes"])
def uninstall_runtime_route(runtime_id: str, purge: bool = Query(default=False)):
    if registry.get_runtime_merged(runtime_id) is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )
    running_rt, config_id = _running_runtime_id()
    if running_rt == runtime_id:
        raise ApiError(
            ErrorCode.RUNTIME_IN_USE,
            f"Runtime '{runtime_id}' is currently serving config '{config_id}'.",
            details={"runtime_id": runtime_id, "config_id": config_id},
            status_code=409,
        )
    install_record.uninstall_runtime(runtime_id, purge=purge)
    return {"ok": True}
