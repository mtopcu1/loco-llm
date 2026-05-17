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
