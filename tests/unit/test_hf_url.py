from __future__ import annotations

import pytest

from llm_cli.core.hf_url import ParsedHFUrl, parse_hf_url, HFUrlError


def test_parse_bare_repo_url():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)


def test_parse_bare_repo_trailing_slash():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)


def test_parse_tree_url_with_revision():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/main")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)


def test_parse_tree_url_with_branch_revision():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/feature-branch")
    assert p == ParsedHFUrl(
        repo="Qwen/Qwen2.5-7B-Instruct", revision="feature-branch", file=None
    )


def test_parse_blob_url():
    p = parse_hf_url(
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf"
    )
    assert p == ParsedHFUrl(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        file="Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf",
    )


def test_parse_resolve_url():
    p = parse_hf_url(
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/resolve/main/weights.gguf"
    )
    assert p.file == "weights.gguf"


def test_parse_blob_nested_file():
    p = parse_hf_url(
        "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/snapshots/abc/file.bin"
    )
    assert p.file == "snapshots/abc/file.bin"


def test_parse_blob_url_missing_file():
    with pytest.raises(HFUrlError, match="missing file path"):
        parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/")
