"""Resolve `${...}` placeholders inside config documents."""
from __future__ import annotations

import copy
import re
from typing import Any

from llm_cli.core.model_registry import RegistryEntry, get_entry
from llm_cli.core.params import ParamValidationError, expand_path
from llm_cli.core.registry import ConfigRecord
from llm_cli.core.settings import Settings


_MODEL_TOKEN_RE = re.compile(r"\$\{model_path\}")


def _resolve_model_path_in(value: str, entry: RegistryEntry, settings: Settings) -> str:
    target = (settings.models_dir / entry.id / entry.artifact.primary).as_posix()
    return _MODEL_TOKEN_RE.sub(target, value)


def resolve_config_for_display(cfg: ConfigRecord, settings: Settings) -> dict[str, Any]:
    """Return a deep copy of config data with display-only path templates expanded."""
    data: dict[str, Any] = copy.deepcopy(cfg.data)
    model_id = data.get("model") if isinstance(data.get("model"), str) else None
    model_entry: RegistryEntry | None = None
    if model_id:
        model_entry = get_entry(settings.models_dir, model_id)
    serve = data.get("serve")
    if isinstance(serve, dict):
        env = serve.get("env")
        if isinstance(env, dict):
            for key, val in list(env.items()):
                if isinstance(val, str):
                    env[key] = val.replace("${data_root}", settings.data_root.as_posix())
        params = serve.get("params")
        if isinstance(params, dict):
            for key, val in list(params.items()):
                if isinstance(val, str):
                    expanded = val
                    if model_entry is not None and "${model_path}" in expanded:
                        expanded = _resolve_model_path_in(expanded, model_entry, settings)
                    try:
                        params[key] = expand_path(expanded, settings)
                    except ParamValidationError:
                        raise
    return data
