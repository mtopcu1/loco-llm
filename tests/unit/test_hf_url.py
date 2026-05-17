from __future__ import annotations

import pytest

from llm_cli.core.hf_url import ParsedHFUrl, parse_hf_url, HFUrlError


def test_parse_bare_repo_url():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)


def test_parse_bare_repo_trailing_slash():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)
