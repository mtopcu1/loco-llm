"""Local model registry persisted as $LLM_MODELS/registry.json."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from llm_cli.core.time import utc_now_iso

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


def registry_path(models_dir: Path) -> Path:
    return models_dir / REGISTRY_FILENAME


def load_registry(models_dir: Path) -> dict[str, RegistryEntry]:
    """Return all entries; an absent file is a clean empty registry."""
    p = registry_path(models_dir)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{p}: malformed registry.json ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{p}: registry.json top-level must be a mapping")
    version = payload.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"{p}: unsupported registry version {version!r}; expected {SCHEMA_VERSION}"
        )
    models = payload.get("models") or {}
    if not isinstance(models, dict):
        raise ValueError(f"{p}: models must be a mapping")
    out: dict[str, RegistryEntry] = {}
    for mid, raw in models.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{p}: entry {mid!r} must be a mapping")
        out[str(mid)] = decode_entry(str(mid), raw)
    return out


def write_registry(models_dir: Path, entries: dict[str, RegistryEntry]) -> Path:
    """Atomically write the registry; creates parent dir if needed."""
    models_dir.mkdir(parents=True, exist_ok=True)
    p = registry_path(models_dir)
    payload = {
        "version": SCHEMA_VERSION,
        "models": {mid: encode_entry(e) for mid, e in sorted(entries.items())},
    }
    fd, tmp_name = tempfile.mkstemp(
        prefix=".registry.", suffix=".tmp", dir=str(models_dir)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        os.replace(tmp_name, p)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return p


def get_entry(models_dir: Path, entry_id: str) -> RegistryEntry | None:
    return load_registry(models_dir).get(entry_id)


def upsert_entry(models_dir: Path, entry: RegistryEntry) -> Path:
    entries = load_registry(models_dir)
    entries[entry.id] = entry
    return write_registry(models_dir, entries)


def remove_entry(models_dir: Path, entry_id: str) -> bool:
    entries = load_registry(models_dir)
    if entry_id not in entries:
        return False
    entries.pop(entry_id)
    write_registry(models_dir, entries)
    return True


class ModelRegistryError(ValueError):
    """Base error for model registry mutations."""


class ModelNotFoundError(ModelRegistryError):
    pass


class ModelAlreadyRegisteredError(ModelRegistryError):
    pass


def _symlink_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.symlink(src, dst)
    except (OSError, NotImplementedError):
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def add_local(models_dir: Path, model_id: str, path: Path, fmt: str) -> RegistryEntry:
    """Register pre-existing local weights under a model id."""
    from llm_cli.core.model_resolve import build_artifact

    if not path.exists():
        raise ModelRegistryError(f"path does not exist: {path}")
    if get_entry(models_dir, model_id) is not None:
        raise ModelAlreadyRegisteredError(f"{model_id!r} already registered")

    target = models_dir / model_id
    target.mkdir(parents=True, exist_ok=True)

    if fmt == "gguf":
        if path.is_file():
            _symlink_or_copy(path, target / path.name)
        elif path.is_dir():
            for entry in sorted(path.iterdir()):
                if entry.suffix.lower() == ".gguf":
                    _symlink_or_copy(entry, target / entry.name)
        else:
            raise ModelRegistryError(f"unsupported gguf path: {path}")
    elif fmt == "safetensors-dir":
        if not path.is_dir():
            raise ModelRegistryError(f"safetensors-dir requires a directory: {path}")
        if not (path / "config.json").is_file():
            raise ModelRegistryError(f"safetensors-dir missing config.json: {path}")
        for entry in sorted(path.iterdir()):
            _symlink_or_copy(entry, target / entry.name)
    else:
        raise ModelRegistryError(f"unknown format {fmt!r}")

    artifact = build_artifact(target, fmt)
    entry = RegistryEntry(
        id=model_id,
        format=fmt,
        source=LocalSource(original_path=str(path.resolve())),
        artifact=artifact,
        metadata=Metadata(display_name=model_id),
        installed_at=utc_now_iso(),
    )
    upsert_entry(models_dir, entry)
    return entry


def uninstall(models_dir: Path, model_id: str, *, purge: bool = False) -> None:
    """Remove a registered model; optionally delete its on-disk directory."""
    if get_entry(models_dir, model_id) is None:
        raise ModelNotFoundError(f"unknown model {model_id!r}")
    remove_entry(models_dir, model_id)
    if purge:
        target = models_dir / model_id
        if target.exists():
            shutil.rmtree(target)
