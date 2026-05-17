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
    load_registry,
    write_registry,
    registry_path,
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


def test_load_missing_returns_empty(tmp_path: Path):
    reg = load_registry(tmp_path)
    assert reg == {}


def test_write_then_load_roundtrip(tmp_path: Path):
    entry = _hf_entry()
    write_registry(tmp_path, {entry.id: entry})
    reg = load_registry(tmp_path)
    assert list(reg.keys()) == [entry.id]
    assert reg[entry.id] == entry
    p = registry_path(tmp_path)
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["version"] == 1
    assert entry.id in on_disk["models"]


def test_load_malformed_raises(tmp_path: Path):
    registry_path(tmp_path).write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="registry.json"):
        load_registry(tmp_path)


def test_load_wrong_version_raises(tmp_path: Path):
    registry_path(tmp_path).write_text(
        json.dumps({"version": 99, "models": {}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unsupported registry version"):
        load_registry(tmp_path)


from llm_cli.core.model_registry import get_entry, upsert_entry, remove_entry


def test_upsert_and_get(tmp_path: Path):
    entry = _hf_entry()
    upsert_entry(tmp_path, entry)
    fetched = get_entry(tmp_path, entry.id)
    assert fetched == entry


def test_get_missing_returns_none(tmp_path: Path):
    assert get_entry(tmp_path, "nope") is None


def test_remove_entry(tmp_path: Path):
    entry = _hf_entry()
    upsert_entry(tmp_path, entry)
    assert remove_entry(tmp_path, entry.id) is True
    assert get_entry(tmp_path, entry.id) is None
    assert remove_entry(tmp_path, entry.id) is False
