from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from llm_cli.core import model_registry
from llm_cli.core.settings import resolve_settings
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
