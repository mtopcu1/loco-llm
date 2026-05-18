"""Tests for model_path binding helpers."""

from llm_cli.core.model_bindings import (
    MODEL_PATH_TOKEN,
    apply_model_bindings,
    bound_keys_to_skip,
)
from llm_cli.core.params import ParamSpec, ParamType


def test_apply_model_bindings_injects_when_model_set() -> None:
    specs = [
        ParamSpec(
            key="model_file",
            type=ParamType.PATH,
            bind="model_path",
        ),
    ]
    raw: dict[str, str] = {}
    out = apply_model_bindings(specs, raw, model_id="some-model-id")
    assert out == {"model_file": MODEL_PATH_TOKEN}


def test_apply_model_bindings_does_not_override_explicit_param() -> None:
    specs = [
        ParamSpec(
            key="model_file",
            type=ParamType.PATH,
            bind="model_path",
        ),
    ]
    raw = {"model_file": "/explicit/path.gguf"}
    out = apply_model_bindings(specs, raw, model_id="some-model-id")
    assert out["model_file"] == "/explicit/path.gguf"


def test_apply_model_bindings_skips_when_no_model() -> None:
    specs = [
        ParamSpec(
            key="model_file",
            type=ParamType.PATH,
            bind="model_path",
        ),
    ]
    raw: dict[str, str] = {}
    out = apply_model_bindings(specs, raw, model_id=None)
    assert out == {}


def test_bound_keys_for_prompt_skip() -> None:
    specs = [
        ParamSpec(key="foo", type=ParamType.STRING, bind=None),
        ParamSpec(key="model_file", type=ParamType.PATH, bind="model_path"),
        ParamSpec(key="bar", type=ParamType.INT, bind="model_path"),
    ]
    assert bound_keys_to_skip(specs, model_id=None) == set()
    assert bound_keys_to_skip(specs, model_id="m1") == {"model_file", "bar"}
