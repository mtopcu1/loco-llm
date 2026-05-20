"""Dashboard install lifecycle helpers."""
from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import yaml

from llm_cli.core.settings import resolve_settings

InstallVerdict = tuple[
    Literal["ok", "missing", "version_mismatch", "hash_mismatch", "dist_missing"],
    str,
]


@dataclass(frozen=True)
class InstalledRecord:
    installed_at: str
    cli_version: str
    node_version: str
    npm_version: str
    dist_hash: str


def dashboard_root() -> Path:
    """Repo-relative path to the dashboard/ source directory."""
    settings = resolve_settings()
    if settings.repo_root is None:
        raise RuntimeError(
            "repo_root not configured. Run `llm setup` or set repo_root via "
            "`llm settings edit repo_root`."
        )
    return settings.repo_root / "dashboard"


def dist_dir() -> Path:
    return dashboard_root() / "dist"


def installed_marker_path() -> Path:
    return dashboard_root() / ".installed"


def compute_dist_hash(dist: Path) -> str:
    """sha256 over sorted (relpath, content_bytes) pairs."""
    h = hashlib.sha256()
    entries = sorted(p for p in dist.rglob("*") if p.is_file())
    for p in entries:
        rel = p.relative_to(dist).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        data = p.read_bytes()
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return f"sha256:{h.hexdigest()}"


def load_installed_record() -> InstalledRecord | None:
    p = installed_marker_path()
    if not p.is_file():
        return None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    try:
        return InstalledRecord(
            installed_at=str(data["installed_at"]),
            cli_version=str(data["cli_version"]),
            node_version=str(data["node_version"]),
            npm_version=str(data["npm_version"]),
            dist_hash=str(data["dist_hash"]),
        )
    except KeyError:
        return None


def write_installed_record(record: InstalledRecord) -> None:
    p = installed_marker_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(asdict(record), sort_keys=False), encoding="utf-8")


def verify_installed(cli_version: str) -> InstallVerdict:
    record = load_installed_record()
    if record is None:
        return ("missing", "dashboard/.installed not found")
    if record.cli_version != cli_version:
        return (
            "version_mismatch",
            f"installed for CLI {record.cli_version}, current is {cli_version}",
        )
    d = dist_dir()
    if not (d / "index.html").is_file():
        return ("dist_missing", "dashboard/dist/index.html not found")
    actual = compute_dist_hash(d)
    if actual != record.dist_hash:
        return ("hash_mismatch", "dist contents differ from recorded hash")
    return ("ok", "")


def _state_dashboard_dir() -> Path:
    settings = resolve_settings()
    if settings.repo_root is None:
        raise RuntimeError("repo_root not configured")
    d = settings.repo_root / "state" / "dashboard"
    d.mkdir(parents=True, exist_ok=True)
    return d


def server_pid_path() -> Path:
    return _state_dashboard_dir() / "server.pid"


def server_log_path() -> Path:
    return _state_dashboard_dir() / "server.log"


def read_server_pid() -> int | None:
    p = server_pid_path()
    if not p.is_file():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def is_server_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
