"""Disk usage scan for the Disk page."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from llm_cli.core.settings import resolve_settings


@dataclass(frozen=True)
class ModelDisk:
    id: str
    bytes: int


@dataclass(frozen=True)
class DiskReport:
    data_root: str
    data_root_bytes_total: int
    data_root_bytes_free: int
    data_root_bytes_used: int
    cache_bytes: int
    models: list[ModelDisk]


def _data_root() -> Path:
    return resolve_settings().data_root


def _models_dir() -> Path:
    return resolve_settings().models_dir


def _cache_dir() -> Path:
    return resolve_settings().cache_dir


def _bytes_of(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def scan() -> DiskReport:
    data_root = _data_root()
    total, used, free = shutil.disk_usage(data_root)

    models_dir = _models_dir()
    models: list[ModelDisk] = []
    if models_dir.is_dir():
        for entry in sorted(models_dir.iterdir()):
            if entry.is_dir():
                models.append(ModelDisk(id=entry.name, bytes=_bytes_of(entry)))

    cache_bytes = _bytes_of(_cache_dir())
    return DiskReport(
        data_root=str(data_root),
        data_root_bytes_total=total,
        data_root_bytes_free=free,
        data_root_bytes_used=used,
        cache_bytes=cache_bytes,
        models=models,
    )
