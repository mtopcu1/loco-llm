"""Persistence of a runtime's `.installed` marker file."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InstallRecord:
    runtime_id: str
    installed_at: str
    build_params: dict[str, Any] = field(default_factory=dict)
    build_sh_sha256: str = ""
    verify_passed: bool | None = None
    schema_hash: str = ""


def record_path(runtimes_dir: Path, runtime_id: str) -> Path:
    """Absolute path of <runtimes_dir>/<id>/.installed."""
    return runtimes_dir / runtime_id / ".installed"


def write_record(runtimes_dir: Path, rec: InstallRecord) -> Path:
    """Write the install record JSON; creates parent dirs as needed."""
    p = record_path(runtimes_dir, rec.runtime_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(asdict(rec), indent=2, sort_keys=True), encoding="utf-8"
    )
    return p


def read_record(runtimes_dir: Path, runtime_id: str) -> InstallRecord | None:
    p = record_path(runtimes_dir, runtime_id)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{p}: corrupt install record ({exc})") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: corrupt install record (top-level not object)")
    return InstallRecord(
        runtime_id=str(raw.get("runtime_id", runtime_id)),
        installed_at=str(raw.get("installed_at", "")),
        build_params=dict(raw.get("build_params") or {}),
        build_sh_sha256=str(raw.get("build_sh_sha256", "")),
        verify_passed=raw.get("verify_passed"),
        schema_hash=str(raw.get("schema_hash", "")),
    )


def is_installed(runtimes_dir: Path, runtime_id: str) -> bool:
    return record_path(runtimes_dir, runtime_id).is_file()


def clear_record(runtimes_dir: Path, runtime_id: str) -> bool:
    p = record_path(runtimes_dir, runtime_id)
    if not p.is_file():
        return False
    p.unlink()
    return True
