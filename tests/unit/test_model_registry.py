from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    LocalSource,
    Metadata,
    RegistryEntry,
    encode_entry,
    decode_entry,
)


def _hf_entry() -> RegistryEntry:
    return RegistryEntry(
        id="unsloth-qwen3.6-235b-a22b__ud-q4-k-xl",
        format="gguf",
        source=HFSource(
            repo="unsloth/Qwen3.6-235B-A22B-GGUF",
            revision="main",
            include=("*UD-Q4_K_XL*",),
            exclude=(),
        ),
        artifact=Artifact(
            primary="model-00001-of-00010.gguf",
            files=("model-00001-of-00010.gguf", "model-00002-of-00010.gguf"),
            total_size_bytes=210432000000,
            sha256={"model-00001-of-00010.gguf": "abc"},
        ),
        metadata=Metadata(
            display_name="Qwen3.6 GGUF",
            license="apache-2.0",
            ctx_length=32768,
        ),
        installed_at="2026-05-17T20:00:00Z",
    )


def test_encode_decode_hf_entry_roundtrip():
    entry = _hf_entry()
    raw = encode_entry(entry)
    assert raw["format"] == "gguf"
    assert raw["source"]["kind"] == "hf"
    assert raw["source"]["include"] == ["*UD-Q4_K_XL*"]
    decoded = decode_entry(entry.id, raw)
    assert decoded == entry


def test_decode_local_entry():
    raw = {
        "format": "safetensors-dir",
        "source": {"kind": "local", "original_path": "/home/u/my"},
        "artifact": {
            "primary": ".",
            "files": ["config.json"],
            "total_size_bytes": 1024,
            "sha256": {},
        },
        "metadata": {"display_name": "My finetune"},
        "installed_at": "2026-05-17T21:00:00Z",
    }
    entry = decode_entry("my-finetune", raw)
    assert isinstance(entry.source, LocalSource)
    assert entry.source.original_path == "/home/u/my"
    assert entry.metadata.ctx_length is None
