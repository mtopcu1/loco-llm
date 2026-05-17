"""Pure helpers for model id derivation and format inference."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from llm_cli.core.hf_url import ParsedHFUrl
from llm_cli.core.model_registry import Artifact


_SLUG_NON_WORD = re.compile(r"[^a-z0-9.]+")
_SHARD_SUFFIX = re.compile(r"-\d{5}-of-\d{5}$", re.IGNORECASE)
_GGUF_SUFFIX = re.compile(r"\.gguf$", re.IGNORECASE)
_GGUF_REPO_SUFFIX = re.compile(r"-gguf$", re.IGNORECASE)


def _slug(token: str) -> str:
    return _SLUG_NON_WORD.sub("-", token.lower()).strip("-")


def _repo_slug(repo: str) -> str:
    owner, _, repo_name = repo.partition("/")
    repo_name = _GGUF_REPO_SUFFIX.sub("", repo_name)
    return f"{_slug(owner)}-{_slug(repo_name)}"


def _repo_base_name(repo: str) -> str:
    """`unsloth/Qwen3.6-235B-A22B-GGUF` -> `Qwen3.6-235B-A22B` (strips trailing -GGUF)."""
    _, _, name = repo.partition("/")
    return _GGUF_REPO_SUFFIX.sub("", name)


def _quant_suffix(filename: str, repo: str) -> str:
    """Pull the quant tag out of a GGUF filename using the repo's base name as prefix."""
    name = filename.rsplit("/", 1)[-1]
    name = _GGUF_SUFFIX.sub("", name)
    name = _SHARD_SUFFIX.sub("", name)
    base = _repo_base_name(repo)
    if base and name.startswith(base):
        name = name[len(base) :].lstrip("-_.")
    return _slug(name)


def derive_model_id(parsed: ParsedHFUrl) -> str:
    """Derive a stable id from a parsed HF URL."""
    base = _repo_slug(parsed.repo)
    if parsed.file is None:
        return base
    suffix = _quant_suffix(parsed.file, parsed.repo)
    return f"{base}__{suffix}" if suffix else base
