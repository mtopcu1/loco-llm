"""Typed parameter system used by runtime build/serve schemas and configs."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParamType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    ENUM = "enum"
    PATH = "path"


@dataclass(frozen=True)
class ParamSpec:
    """A single typed parameter declared in a runtime manifest."""

    key: str
    type: ParamType
    default: Any = None
    required: bool = False
    prompt: str | None = None
    env: str | None = None
    values: tuple[str, ...] = field(default_factory=tuple)  # only for enum


def _coerce_type(raw: Any) -> ParamType:
    if not isinstance(raw, str):
        raise ValueError(f"param type must be a string, got {raw!r}")
    try:
        return ParamType(raw)
    except ValueError as exc:
        raise ValueError(
            f"unknown param type {raw!r}; "
            f"valid: {', '.join(t.value for t in ParamType)}"
        ) from exc


def parse_schema(raw: dict[str, Any]) -> list[ParamSpec]:
    """Parse a manifest schema mapping (`build:` or `serve:`) into ParamSpecs."""
    if not isinstance(raw, dict):
        raise ValueError(f"schema must be a mapping, got {type(raw).__name__}")
    out: list[ParamSpec] = []
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"param {key!r}: entry must be a mapping")
        ptype = _coerce_type(entry.get("type"))
        values: tuple[str, ...] = ()
        if ptype is ParamType.ENUM:
            raw_values = entry.get("values")
            if not isinstance(raw_values, list) or not raw_values:
                raise ValueError(
                    f"param {key!r}: enum requires a non-empty values list"
                )
            values = tuple(str(v) for v in raw_values)
        out.append(
            ParamSpec(
                key=str(key),
                type=ptype,
                default=entry.get("default"),
                required=bool(entry.get("required", False)),
                prompt=(
                    str(entry["prompt"]) if entry.get("prompt") is not None else None
                ),
                env=str(entry["env"]) if entry.get("env") is not None else None,
                values=values,
            )
        )
    return out
