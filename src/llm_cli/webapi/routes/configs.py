from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from llm_cli.core import registry
from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core import lifecycle_status
from llm_cli.core.param_grid_build import cells_from_specs
from llm_cli.core.scaffold import scaffold_root
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


def _get_config_or_404(config_id: str):
    cfg = registry.get_config_merged(config_id)
    if cfg is None:
        raise ApiError(
            ErrorCode.CONFIG_NOT_FOUND,
            f"Config '{config_id}' not found",
            details={"config_id": config_id},
            status_code=404,
        )
    return cfg


@router.get("/configs", tags=["configs"])
def list_configs():
    return [
        {"id": cfg.id, "source": cfg.source, "data": cfg.data}
        for cfg in registry.discover_configs_merged()
    ]


@router.get("/configs/{config_id}", tags=["configs"])
def get_config(config_id: str):
    cfg = _get_config_or_404(config_id)
    settings = resolve_settings()
    resolved = resolve_config_for_display(cfg, settings)
    return {"id": cfg.id, "source": cfg.source, "raw": cfg.data, "resolved": resolved}


@router.get("/configs/{config_id}/params", tags=["configs"])
def get_config_params(config_id: str):
    cfg = _get_config_or_404(config_id)
    runtime_id = str(cfg.data.get("runtime", ""))
    manifest = registry.get_runtime_manifest_merged(runtime_id)
    if manifest is None:
        raise ApiError(
            ErrorCode.RUNTIME_NOT_FOUND,
            f"Runtime '{runtime_id}' not found",
            details={"runtime_id": runtime_id, "config_id": config_id},
            status_code=404,
        )

    serve = cfg.data.get("serve") if isinstance(cfg.data.get("serve"), dict) else {}
    values: dict[str, str] = {}
    if isinstance(serve, dict) and isinstance(serve.get("params"), dict):
        values = {str(k): str(v) for k, v in serve["params"].items()}

    cells = cells_from_specs(manifest.serve_schema, values=values)
    return [asdict(cell) for cell in cells]


@router.get("/configs/{config_id}/validate", tags=["configs"])
def validate_config(config_id: str):
    cfg = _get_config_or_404(config_id)
    errors, _warnings = registry.validate_config_v2(scaffold_root(), cfg)
    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/configs", tags=["configs"])
def create_config(body: dict[str, Any]):
    try:
        cfg = registry.write_config(body, overwrite=False, via="api")
    except registry.ConfigAlreadyExistsError as exc:
        raise ApiError(
            ErrorCode.CONFIG_ALREADY_EXISTS,
            str(exc),
            details={"config_id": str(body.get("id", ""))},
            status_code=409,
        ) from exc
    except registry.ConfigValidationError as exc:
        raise ApiError(
            ErrorCode.CONFIG_INVALID,
            "Configuration validation failed",
            details={"config_id": str(body.get("id", "")), "errors": exc.errors},
            status_code=400,
        ) from exc
    return {"id": cfg.id, "source": cfg.source, "data": cfg.data}


@router.put("/configs/{config_id}", tags=["configs"])
def update_config(config_id: str, body: dict[str, Any]):
    if registry.get_config_merged(config_id) is None:
        raise ApiError(
            ErrorCode.CONFIG_NOT_FOUND,
            f"Config '{config_id}' not found",
            details={"config_id": config_id},
            status_code=404,
        )
    payload = dict(body)
    payload["id"] = config_id
    try:
        cfg = registry.write_config(payload, overwrite=True, via="api")
    except registry.ConfigValidationError as exc:
        raise ApiError(
            ErrorCode.CONFIG_INVALID,
            "Configuration validation failed",
            details={"config_id": config_id, "errors": exc.errors},
            status_code=400,
        ) from exc
    return {"id": cfg.id, "source": cfg.source, "data": cfg.data}


@router.delete("/configs/{config_id}", tags=["configs"])
def delete_config_route(config_id: str):
    running_id = lifecycle_status.running_config_id()
    if running_id == config_id:
        raise ApiError(
            ErrorCode.CONFIG_IN_USE,
            f"Config '{config_id}' is currently running",
            details={"config_id": config_id},
            status_code=409,
        )
    try:
        registry.delete_config(config_id)
    except registry.ConfigNotFoundInUserLayerError as exc:
        raise ApiError(
            ErrorCode.CONFIG_NOT_FOUND,
            str(exc),
            details={"config_id": config_id},
            status_code=404,
        ) from exc
    return {"ok": True}
