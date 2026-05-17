# tests/unit/test_params.py
from __future__ import annotations

import pytest

from llm_cli.core.params import ParamSpec, ParamType, parse_schema


def test_parse_schema_empty():
    assert parse_schema({}) == []


def test_parse_schema_basic_types():
    raw = {
        "flavor": {"type": "enum", "values": ["cuda", "cpu"], "default": "cuda"},
        "jobs": {"type": "int", "default": 0, "prompt": "Parallel jobs"},
        "ctx": {"type": "int", "default": 8192, "required": False},
        "name": {"type": "string", "required": True},
    }
    specs = parse_schema(raw)
    by_key = {s.key: s for s in specs}
    assert by_key["flavor"].type is ParamType.ENUM
    assert by_key["flavor"].values == ("cuda", "cpu")
    assert by_key["flavor"].default == "cuda"
    assert by_key["jobs"].type is ParamType.INT
    assert by_key["jobs"].prompt == "Parallel jobs"
    assert by_key["name"].required is True
    assert by_key["ctx"].required is False


def test_parse_schema_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown param type"):
        parse_schema({"x": {"type": "blob"}})


def test_parse_schema_enum_requires_values():
    with pytest.raises(ValueError, match="enum .* values"):
        parse_schema({"x": {"type": "enum"}})
