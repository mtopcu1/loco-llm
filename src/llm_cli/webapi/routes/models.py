from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from llm_cli.core import jobs as jobs_module, model_registry
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.job_runners import model_pull_job
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


def _entry_payload(entry: model_registry.RegistryEntry) -> dict[str, Any]:
    return {"id": entry.id, **model_registry.encode_entry(entry)}


@router.get("/models", tags=["models"])
def list_models():
    settings = resolve_settings()
    entries = model_registry.load_registry(settings.models_dir)
    return [_entry_payload(entry) for entry in entries.values()]


@router.get("/models/{model_id}", tags=["models"])
def get_model(model_id: str):
    settings = resolve_settings()
    entry = model_registry.get_entry(settings.models_dir, model_id)
    if entry is None:
        raise ApiError(
            ErrorCode.MODEL_NOT_FOUND,
            f"Model '{model_id}' not found",
            details={"model_id": model_id},
            status_code=404,
        )
    return _entry_payload(entry)


class PullModelBody(BaseModel):
    url: str
    id: str | None = None
    format: str | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    force: bool = False


class AddLocalModelBody(BaseModel):
    id: str
    path: str
    format: str


@router.post("/models/pull", tags=["models"])
def pull_model(body: PullModelBody):
    async def factory(report):
        await model_pull_job(
            url=body.url,
            fmt=body.format,
            include=body.include,
            exclude=body.exclude,
            id_override=body.id,
            force=body.force,
            report=report,
        )

    job_id = jobs_module.registry().start_async(
        kind="model_pull",
        context={"url": body.url, "id": body.id},
        coro_factory=factory,
    )
    return {"job_id": job_id}


@router.post("/models/add", tags=["models"])
def add_local_model(body: AddLocalModelBody):
    settings = resolve_settings()
    from pathlib import Path

    try:
        entry = model_registry.add_local(
            settings.models_dir,
            body.id,
            Path(body.path),
            body.format,
        )
    except model_registry.ModelAlreadyRegisteredError as exc:
        raise ApiError(
            ErrorCode.MODEL_ALREADY_REGISTERED,
            str(exc),
            details={"model_id": body.id},
            status_code=409,
        ) from exc
    except model_registry.ModelRegistryError as exc:
        raise ApiError(
            ErrorCode.VALIDATION_ERROR,
            str(exc),
            details={"model_id": body.id},
            status_code=400,
        ) from exc
    return _entry_payload(entry)


@router.delete("/models/{model_id}", tags=["models"])
def uninstall_model(model_id: str, purge: bool = Query(default=False)):
    settings = resolve_settings()
    try:
        model_registry.uninstall(settings.models_dir, model_id, purge=purge)
    except model_registry.ModelNotFoundError as exc:
        raise ApiError(
            ErrorCode.MODEL_NOT_FOUND,
            str(exc),
            details={"model_id": model_id},
            status_code=404,
        ) from exc
    return {"ok": True}
