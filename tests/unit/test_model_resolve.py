from __future__ import annotations

import pytest

from llm_cli.core.hf_url import ParsedHFUrl
from llm_cli.core.model_resolve import derive_model_id


def test_derive_id_safetensors_repo():
    p = ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)
    assert derive_model_id(p) == "qwen-qwen2.5-7b-instruct"


def test_derive_id_gguf_file():
    p = ParsedHFUrl(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        file="Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf",
    )
    assert derive_model_id(p) == "unsloth-qwen3.6-235b-a22b__ud-q4-k-xl"


def test_derive_id_gguf_single_file_no_shard():
    p = ParsedHFUrl(
        repo="bartowski/Foo-GGUF",
        revision="main",
        file="Foo-Q5_K_M.gguf",
    )
    assert derive_model_id(p) == "bartowski-foo__q5-k-m"


def test_derive_id_gguf_file_when_name_equals_repo_base():
    p = ParsedHFUrl(
        repo="o/Foo-GGUF",
        revision="main",
        file="Foo.gguf",
    )
    # When stripping the repo's base name from the file leaves nothing, drop the suffix.
    assert derive_model_id(p) == "o-foo"


from llm_cli.core.model_resolve import (
    InferResult,
    FormatInferenceError,
    infer_format,
)


def _files(*names: str) -> list[str]:
    return list(names)


def test_infer_format_url_with_gguf_file():
    p = ParsedHFUrl(repo="o/r", revision="main", file="weights.gguf")
    r = infer_format(p, _files("weights.gguf", "config.json"))
    assert r == InferResult(format="gguf", include=("weights.gguf",))


def test_infer_format_url_with_unsupported_file_errors():
    p = ParsedHFUrl(repo="o/r", revision="main", file="model.bin")
    with pytest.raises(FormatInferenceError, match="--format and/or --include"):
        infer_format(p, _files("model.bin"))


def test_infer_format_repo_single_gguf():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    r = infer_format(p, _files("only-Q4.gguf", "README.md"))
    assert r.format == "gguf"
    assert r.include == ("only-Q4.gguf",)


def test_infer_format_repo_safetensors_dir():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files("config.json", "tokenizer.json", "model-00001-of-00004.safetensors")
    r = infer_format(p, files)
    assert r.format == "safetensors-dir"
    assert r.include == ()


def test_infer_format_repo_multiple_gguf_quants_errors():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files("model-Q4_K_M.gguf", "model-Q5_K_M.gguf")
    with pytest.raises(FormatInferenceError, match="multiple GGUF"):
        infer_format(p, files)


def test_infer_format_mixed_repo_errors():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files("model-Q4_K_M.gguf", "config.json", "model.safetensors")
    with pytest.raises(FormatInferenceError, match="mix"):
        infer_format(p, files)


def test_infer_format_split_gguf_one_family_ok():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files(
        "model-Q4_K_M-00001-of-00003.gguf",
        "model-Q4_K_M-00002-of-00003.gguf",
        "model-Q4_K_M-00003-of-00003.gguf",
    )
    r = infer_format(p, files)
    assert r.format == "gguf"
    assert sorted(r.include) == sorted(files)
