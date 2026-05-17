"""Typed parameter system used by runtime build/serve schemas and configs."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from llm_cli.core.settings import Settings


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


class ParamValidationError(ValueError):
    """Raised when a value cannot be coerced/validated against its ParamSpec."""


_TOKEN_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _settings_tokens(s: Settings) -> dict[str, str]:
    return {
        "data_root": s.data_root.as_posix(),
        "repo_root": s.repo_root.as_posix(),
        "runtimes_dir": s.runtimes_dir.as_posix(),
        "models_dir": s.models_dir.as_posix(),
        "cache_dir": s.cache_dir.as_posix(),
    }


def expand_path(raw: str, settings: Settings) -> str:
    """Expand ${data_root}/${runtimes_dir}/... and leading ~ in a path string.

    Unknown ${...} tokens raise ParamValidationError. No shell is involved.
    """
    tokens = _settings_tokens(settings)
    if raw.startswith("~"):
        home = os.environ.get("HOME")
        if (
            home is not None
            and (raw == "~" or (len(raw) > 1 and raw[1] in "/\\"))
        ):
            suffix = (
                raw[2:].replace("\\", "/").lstrip("/")
                if len(raw) > 2
                else ""
            )
            base = Path(home)
            expanded = (
                str((base / suffix).as_posix()) if suffix else str(base.as_posix())
            )
        else:
            expanded = str(Path(raw).expanduser())
    else:
        expanded = raw

    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in tokens:
            raise ParamValidationError(
                f"unknown template token ${{{name}}}; "
                f"valid: {', '.join(sorted(tokens))}"
            )
        return tokens[name]

    return _TOKEN_RE.sub(_sub, expanded)


_BOOL_TRUE = {"true", "1", "yes", "y", "on"}
_BOOL_FALSE = {"false", "0", "no", "n", "off"}


def coerce_value(spec: ParamSpec, raw: Any) -> Any:
    """Coerce a YAML scalar / CLI string into the spec's declared type.

    Path expansion is handled separately by `expand_path` after coercion;
    here we only validate that the raw value is a non-empty string-ish.
    """
    if spec.type is ParamType.STRING:
        return str(raw)
    if spec.type is ParamType.INT:
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ParamValidationError(
                f"param {spec.key!r}: expected int, got {raw!r}"
            ) from exc
    if spec.type is ParamType.FLOAT:
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ParamValidationError(
                f"param {spec.key!r}: expected float, got {raw!r}"
            ) from exc
    if spec.type is ParamType.BOOL:
        if isinstance(raw, bool):
            return raw
        token = str(raw).strip().lower()
        if token in _BOOL_TRUE:
            return True
        if token in _BOOL_FALSE:
            return False
        raise ParamValidationError(
            f"param {spec.key!r}: expected bool, got {raw!r}"
        )
    if spec.type is ParamType.ENUM:
        token = str(raw)
        if token not in spec.values:
            raise ParamValidationError(
                f"param {spec.key!r}: must be one of "
                f"{', '.join(spec.values)}; got {raw!r}"
            )
        return token
    if spec.type is ParamType.PATH:
        return str(raw)
    raise ParamValidationError(f"param {spec.key!r}: unhandled type {spec.type!r}")
