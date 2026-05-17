"""Resolve `${data_root}` placeholders inside config documents."""
from __future__ import annotations

import copy
from typing import Any

from llm_cli.core.params import ParamValidationError, expand_path
from llm_cli.core.registry import ConfigRecord
from llm_cli.core.settings import Settings


def resolve_config_for_display(cfg: ConfigRecord, settings: Settings) -> dict[str, Any]:
    """Return a deep copy of config data with display-only path templates expanded."""
    data: dict[str, Any] = copy.deepcopy(cfg.data)
    root = settings.data_root.as_posix()
    serve = data.get("serve")
    if isinstance(serve, dict):
        env = serve.get("env")
        if isinstance(env, dict):
            for key, val in list(env.items()):
                if isinstance(val, str):
                    env[key] = val.replace("${data_root}", root)
        params = serve.get("params")
        if isinstance(params, dict):
            for key, val in list(params.items()):
                if isinstance(val, str):
                    try:
                        params[key] = expand_path(val, settings)
                    except ParamValidationError:
                        raise
    return data
