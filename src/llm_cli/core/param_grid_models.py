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
    default: str
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


def cell_state(cell: ParamCell) -> Literal["readonly", "modified", "default"]:
    """Semantic row state used for styling in grid and plain renderers."""
    if cell.readonly:
        return "readonly"
    if cell.value != cell.default:
        return "modified"
    return "default"
