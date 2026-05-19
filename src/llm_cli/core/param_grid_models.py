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


def cell_state(cell: ParamCell) -> Literal["locked", "disabled", "enabled-empty", "enabled-set"]:
    """Semantic row state used for styling in grid and plain renderers."""
    if cell.locked or cell.readonly:
        return "locked"
    if not cell.enabled:
        return "disabled"
    if not str(cell.value).strip() and cell.param_type is not ParamType.BOOL:
        return "enabled-empty"
    return "enabled-set"
