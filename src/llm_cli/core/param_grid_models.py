"""Data types for param grid UI (TTY and plain fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from llm_cli.core.params import ParamType


@dataclass
class ParamCell:
    key: str
    label: str
    description: str
    value: str
    enabled: bool = False
    locked: bool = False
    readonly: bool = False
    tier: str = "common"
    hint: str | None = None
    param_type: ParamType = ParamType.STRING


@dataclass
class MetaField:
    key: str
    label: str
    value: str
    description: str = ""


@dataclass
class ParamGridResult:
    values: dict[str, str]
    meta: dict[str, str]
    action: Literal["save", "abort"]
    advanced_revealed: bool = False


def load_defaults_for_runtime(runtime_id: str, *, model_id: str | None = None) -> list[ParamCell]:
    """Default ParamCells for a fresh config (wizard / default-params API)."""
    from llm_cli.core import registry
    from llm_cli.core.config_resolve import _resolve_model_path_in
    from llm_cli.core.model_bindings import apply_model_bindings, bound_keys_to_skip
    from llm_cli.core.model_registry import get_entry
    from llm_cli.core.param_grid_build import cells_from_specs
    from llm_cli.core.settings import resolve_settings

    manifest = registry.get_runtime_manifest_merged(runtime_id)
    if manifest is None:
        raise KeyError(runtime_id)

    values = apply_model_bindings(manifest.serve_schema, {}, model_id=model_id)
    if model_id:
        settings = resolve_settings()
        entry = get_entry(settings.models_dir, model_id)
        if entry is not None:
            for key, val in list(values.items()):
                if "${model_path}" in val:
                    values[key] = _resolve_model_path_in(val, entry, settings)

    skip_keys = bound_keys_to_skip(manifest.serve_schema, model_id=model_id)
    return cells_from_specs(
        manifest.serve_schema,
        values=values,
        skip_keys=skip_keys,
        readonly_keys=skip_keys,
    )


def cell_state(cell: ParamCell) -> Literal["locked", "disabled", "enabled-empty", "enabled-set"]:
    """Semantic row state used for styling in grid and plain renderers."""
    if cell.locked or cell.readonly:
        return "locked"
    if not cell.enabled:
        return "disabled"
    if not str(cell.value).strip() and cell.param_type is not ParamType.BOOL:
        return "enabled-empty"
    return "enabled-set"
