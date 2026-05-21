# tests/unit/test_params.py
from __future__ import annotations

import pytest

from llm_cli.core.params import (
    ParamSpec,
    ParamType,
    ParamValidationError,
    coerce_value,
    derive_env_name,
    evaluate_when,
    parse_schema,
    validate_params,
)


def test_parse_schema_empty():
    assert parse_schema({}) == []


def test_parse_schema_basic_types():
    raw = {
        "flavor": {"type": "enum", "values": ["cuda", "cpu"]},
        "jobs": {"type": "int", "prompt": "Parallel jobs"},
        "ctx": {"type": "int", "required": False},
        "name": {"type": "string", "required": True},
    }
    specs = parse_schema(raw)
    by_key = {s.key: s for s in specs}
    assert by_key["flavor"].type is ParamType.ENUM
    assert by_key["flavor"].values == ("cuda", "cpu")
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


def test_parse_schema_reads_bind_model_path():
    from llm_cli.core.params import parse_schema

    specs = parse_schema(
        {
            "gguf_path": {
                "type": "path",
                "required": True,
                "bind": "model_path",
                "tier": "common",
            }
        }
    )
    assert len(specs) == 1
    assert specs[0].bind == "model_path"


def test_parse_schema_rejects_unknown_bind():
    from llm_cli.core.params import parse_schema
    import pytest

    with pytest.raises(ValueError, match="bind"):
        parse_schema({"x": {"type": "string", "bind": "other"}})


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


from pathlib import Path

from llm_cli.core.params import expand_path
from llm_cli.core.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        repo_root=tmp_path / "repo",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
    )


def test_expand_path_tokens(tmp_path):
    s = _settings(tmp_path)
    assert expand_path("${data_root}/x", s) == str((tmp_path / "data" / "x").as_posix())
    assert expand_path("${models_dir}/m.gguf", s) == str(
        (tmp_path / "data" / "models" / "m.gguf").as_posix()
    )


def test_expand_path_repo_root_none_uses_install_root(tmp_path, monkeypatch):
    install = tmp_path / "install"
    install.mkdir()
    monkeypatch.setenv("LOCO_INSTALL", str(install))
    s = Settings(
        data_root=tmp_path / "data",
        repo_root=None,
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
    )
    assert expand_path("${repo_root}/runtimes", s) == str((install / "runtimes").as_posix())


def test_expand_path_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    s = _settings(tmp_path)
    assert expand_path("~/foo", s).endswith("/foo")


def test_expand_path_unknown_token_raises(tmp_path):
    s = _settings(tmp_path)
    with pytest.raises(ParamValidationError, match="unknown template token"):
        expand_path("${nope}/x", s)


def test_expand_path_passthrough_when_no_token(tmp_path):
    s = _settings(tmp_path)
    assert expand_path("/abs/path", s) == "/abs/path"


def test_derive_env_name_uses_declared_env():
    spec = _spec("gguf_path", "path", env="LLM_LLAMACPP_GGUF")
    assert derive_env_name(spec, runtime_id="llamacpp") == "LLM_LLAMACPP_GGUF"


def test_derive_env_name_fallback_runtime_serve():
    spec = _spec("ctx", "int")
    assert derive_env_name(spec, runtime_id="llamacpp") == "LLM_LLAMACPP_CTX"


def test_derive_env_name_fallback_build():
    spec = _spec("flavor", "enum", values=["a", "b"])
    assert derive_env_name(spec, runtime_id="llamacpp", scope="build") == "LLM_BUILD_FLAVOR"


def test_derive_env_name_normalizes_dashes():
    spec = _spec("n-gpu-layers", "int")
    assert derive_env_name(spec, runtime_id="llamacpp") == "LLM_LLAMACPP_N_GPU_LAYERS"


def test_evaluate_when_none_passes():
    assert evaluate_when(None, build_params={"flavor": "cuda"}) is True
    assert evaluate_when({}, build_params={"flavor": "cuda"}) is True


def test_evaluate_when_matches():
    assert evaluate_when(
        {"build.flavor": "cuda"}, build_params={"flavor": "cuda"}
    ) is True


def test_evaluate_when_mismatches():
    assert evaluate_when(
        {"build.flavor": "cuda"}, build_params={"flavor": "cpu"}
    ) is False


def test_evaluate_when_param_absent_means_unknown():
    assert evaluate_when({"build.flavor": "cuda"}, build_params={}) is False


def test_evaluate_when_rejects_non_build_prefix():
    with pytest.raises(ValueError, match="only supports build"):
        evaluate_when({"serve.host": "x"}, build_params={})


def test_parse_schema_rejects_default_key():
    with pytest.raises(ValueError, match="default.*removed"):
        parse_schema({"ctx": {"type": "int", "default": 8192}})


def test_validate_params_does_not_fill_missing_optional():
    specs = parse_schema({"ctx": {"type": "int"}, "host": {"type": "string"}})
    out, errors = validate_params(specs, {})
    assert errors == []
    assert out == {}


def test_validate_params_required_still_errors_when_missing():
    specs = parse_schema({"name": {"type": "string", "required": True}})
    out, errors = validate_params(specs, {})
    assert out == {}
    assert any("required" in e for e in errors)


def test_validate_params_required_missing_errors():
    specs = parse_schema({"name": {"type": "string", "required": True}})
    out, errors = validate_params(specs, {})
    assert out == {}
    assert any("name" in e and "required" in e for e in errors)


def test_validate_params_unknown_key_errors():
    specs = parse_schema({"ctx": {"type": "int"}})
    out, errors = validate_params(specs, {"ctxx": 16})
    assert out == {}
    assert any("unknown" in e and "ctxx" in e for e in errors)


def test_validate_params_type_mismatch_errors():
    specs = parse_schema({"ctx": {"type": "int"}})
    out, errors = validate_params(specs, {"ctx": "huge"})
    assert out == {}
    assert any("ctx" in e for e in errors)


def test_validate_params_returns_coerced():
    specs = parse_schema({"jobs": {"type": "int"}})
    out, errors = validate_params(specs, {"jobs": "4"})
    assert errors == []
    assert out == {"jobs": 4}
