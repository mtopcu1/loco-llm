from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from llm_cli.core.settings import (
    KEY_REGISTRY,
    SettingsValidationError,
    UnknownSettingError,
    load_settings,
    resolve_settings,
    set as set_setting,
)
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


class SettingUpdateBody(BaseModel):
    value: str | None


def _settings_payload() -> dict:
    resolved = resolve_settings()
    return {
        "stored": load_settings(),
        "resolved": {
            "data_root": str(resolved.data_root),
            "repo_root": str(resolved.repo_root) if resolved.repo_root else None,
            "runtimes_dir": str(resolved.runtimes_dir),
            "models_dir": str(resolved.models_dir),
            "cache_dir": str(resolved.cache_dir),
        },
        "registry": [
            {"key": key, **{k: v for k, v in value.items() if k != "default"}}
            for key, value in KEY_REGISTRY.items()
        ],
    }


@router.get("/settings", tags=["settings"])
def get_settings():
    return _settings_payload()


@router.put("/settings/{key}", tags=["settings"])
def update_setting(key: str, body: SettingUpdateBody):
    try:
        set_setting(key, body.value)
    except UnknownSettingError as exc:
        raise ApiError(
            ErrorCode.SETTINGS_UNKNOWN_KEY,
            str(exc),
            details={"key": key},
            status_code=404,
        ) from exc
    except SettingsValidationError as exc:
        raise ApiError(
            ErrorCode.SETTINGS_VALIDATION_FAILED,
            str(exc),
            details={"key": key},
            status_code=400,
        ) from exc
    return _settings_payload()
