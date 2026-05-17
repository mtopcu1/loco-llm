# tests/unit/test_params.py
from __future__ import annotations

import pytest

from llm_cli.core.params import (
    ParamSpec,
    ParamType,
    ParamValidationError,
    coerce_value,
    parse_schema,
)


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


def _spec(key: str, type_: str, **kw) -> ParamSpec:
    return parse_schema({key: {"type": type_, **kw}})[0]


def test_coerce_string_passes_through():
    assert coerce_value(_spec("x", "string"), "hi") == "hi"


def test_coerce_int_parses_string_and_int():
    assert coerce_value(_spec("x", "int"), 42) == 42
    assert coerce_value(_spec("x", "int"), "42") == 42


def test_coerce_int_rejects_garbage():
    with pytest.raises(ParamValidationError):
        coerce_value(_spec("x", "int"), "fourty-two")


def test_coerce_float_parses():
    assert coerce_value(_spec("x", "float"), 1.5) == 1.5
    assert coerce_value(_spec("x", "float"), "0.9") == 0.9


def test_coerce_bool_accepts_true_false_strings():
    spec = _spec("x", "bool")
    for val in (True, "true", "1", "yes"):
        assert coerce_value(spec, val) is True
    for val in (False, "false", "0", "no"):
        assert coerce_value(spec, val) is False


def test_coerce_bool_rejects_other():
    with pytest.raises(ParamValidationError):
        coerce_value(_spec("x", "bool"), "maybe")


def test_coerce_enum_accepts_listed():
    spec = _spec("x", "enum", values=["a", "b"])
    assert coerce_value(spec, "a") == "a"


def test_coerce_enum_rejects_unlisted():
    spec = _spec("x", "enum", values=["a", "b"])
    with pytest.raises(ParamValidationError, match="must be one of"):
        coerce_value(spec, "c")
