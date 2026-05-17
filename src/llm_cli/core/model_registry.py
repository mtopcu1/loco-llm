"""Local model registry persisted as $LLM_MODELS/registry.json."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

REGISTRY_FILENAME = "registry.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HFSource:
    kind: str = "hf"
    repo: str = ""
    revision: str = "main"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocalSource:
    kind: str = "local"
    original_path: str = ""


Source = Union[HFSource, LocalSource]


@dataclass(frozen=True)
class Artifact:
    primary: str
    files: tuple[str, ...]
    total_size_bytes: int
    sha256: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Metadata:
    display_name: str = ""
    license: str | None = None
    ctx_length: int | None = None


@dataclass(frozen=True)
class RegistryEntry:
    id: str
    format: str
    source: Source
    artifact: Artifact
    metadata: Metadata
    installed_at: str


def _encode_source(src: Source) -> dict[str, Any]:
    if isinstance(src, HFSource):
        return {
            "kind": "hf",
            "repo": src.repo,
            "revision": src.revision,
            "include": list(src.include),
            "exclude": list(src.exclude),
        }
    if isinstance(src, LocalSource):
        return {"kind": "local", "original_path": src.original_path}
    raise TypeError(f"unknown source type: {type(src).__name__}")


def encode_entry(entry: RegistryEntry) -> dict[str, Any]:
    return {
        "format": entry.format,
        "source": _encode_source(entry.source),
        "artifact": {
            "primary": entry.artifact.primary,
            "files": list(entry.artifact.files),
            "total_size_bytes": entry.artifact.total_size_bytes,
            "sha256": dict(entry.artifact.sha256),
        },
        "metadata": {
            "display_name": entry.metadata.display_name,
            "license": entry.metadata.license,
            "ctx_length": entry.metadata.ctx_length,
        },
        "installed_at": entry.installed_at,
    }


def _decode_source(raw: dict[str, Any]) -> Source:
    kind = str(raw.get("kind", ""))
    if kind == "hf":
        return HFSource(
            repo=str(raw.get("repo", "")),
            revision=str(raw.get("revision", "main")),
            include=tuple(str(p) for p in (raw.get("include") or [])),
            exclude=tuple(str(p) for p in (raw.get("exclude") or [])),
        )
    if kind == "local":
        return LocalSource(original_path=str(raw.get("original_path", "")))
    raise ValueError(f"unknown source kind {kind!r}")


def decode_entry(entry_id: str, raw: dict[str, Any]) -> RegistryEntry:
    art = raw.get("artifact") or {}
    md = raw.get("metadata") or {}
    return RegistryEntry(
        id=entry_id,
        format=str(raw["format"]),
        source=_decode_source(raw.get("source") or {}),
        artifact=Artifact(
            primary=str(art.get("primary", "")),
            files=tuple(str(p) for p in (art.get("files") or [])),
            total_size_bytes=int(art.get("total_size_bytes") or 0),
            sha256={str(k): str(v) for k, v in (art.get("sha256") or {}).items()},
        ),
        metadata=Metadata(
            display_name=str(md.get("display_name", "")),
            license=str(md["license"]) if md.get("license") is not None else None,
            ctx_length=int(md["ctx_length"]) if md.get("ctx_length") is not None else None,
        ),
        installed_at=str(raw.get("installed_at", "")),
    )
