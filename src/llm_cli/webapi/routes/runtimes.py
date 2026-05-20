from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from llm_cli.core import install_record, registry
from llm_cli.core.settings import resolve_settings
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
