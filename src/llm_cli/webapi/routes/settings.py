from __future__ import annotations

from fastapi import APIRouter

from llm_cli.core.settings import KEY_REGISTRY, load_settings, resolve_settings

router = APIRouter()


@router.get("/settings", tags=["settings"])
def get_settings():
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
