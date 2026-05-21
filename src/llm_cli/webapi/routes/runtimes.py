from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from llm_cli.core import install_record, jobs as jobs_module, lifecycle_status, param_grid_models as pgm, registry
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.job_runners import runtime_install_job, runtime_rebuild_job
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


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
                has_metrics=bool(rt.raw.get("metrics")),
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


@router.get("/runtimes/{runtime_id}/default-params", tags=["runtimes"])
def default_params(runtime_id: str, model_id: str | None = None):
    if registry.get_runtime_merged(runtime_id) is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )
    try:
        cells = pgm.load_defaults_for_runtime(runtime_id, model_id=model_id)
    except KeyError as exc:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        ) from exc
    return [asdict(cell) for cell in cells]


@router.post("/runtimes/{runtime_id}/install", tags=["runtimes"])
def install_runtime_route(runtime_id: str):
    if registry.get_runtime_merged(runtime_id) is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id},
            status_code=404,
        )

    async def factory(report):
        await runtime_install_job(runtime_id, report)

    job_id = jobs_module.registry().start_async(
        kind="runtime_install",
        context={"runtime_id": runtime_id},
        coro_factory=factory,
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
    async def factory(report):
        await runtime_rebuild_job(runtime_id, reset=reset, report=report)

    job_id = jobs_module.registry().start_async(
        kind="runtime_rebuild",
        context={"runtime_id": runtime_id, "reset": reset},
        coro_factory=factory,
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
    running_rt, config_id = lifecycle_status.running_runtime_and_config()
    if running_rt == runtime_id:
        raise ApiError(
            ErrorCode.RUNTIME_IN_USE,
            f"Runtime '{runtime_id}' is currently serving config '{config_id}'.",
            details={"runtime_id": runtime_id, "config_id": config_id},
            status_code=409,
        )
    install_record.uninstall_runtime(runtime_id, purge=purge)
    return {"ok": True}
