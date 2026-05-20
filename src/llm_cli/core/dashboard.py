"""Dashboard install lifecycle helpers."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
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


def _probe_node_version() -> str:
    try:
        out = subprocess.check_output(["node", "--version"], text=True).strip()
        return out.lstrip("v")
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "`node` not found. Install Node.js 20+ (https://nodejs.org) and retry."
        ) from exc


def _probe_npm_version() -> str:
    try:
        return subprocess.check_output(["npm", "--version"], text=True).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "`npm` not found. Install Node.js 20+ (includes npm) and retry."
        ) from exc


def _check_node_minimum(version: str, minimum: tuple[int, int] = (20, 0)) -> None:
    major_minor = tuple(int(part) for part in version.split(".")[:2])
    if major_minor < minimum:
        need = ".".join(str(part) for part in minimum)
        raise RuntimeError(f"Node.js {need}+ required; found {version}.")


def _managed_venv_python(root: Path) -> Path | None:
    candidates = (
        root.parent / ".venv" / "Scripts" / "python.exe",
        root.parent / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def run_install(
    *,
    cli_version: str,
    skip_python: bool,
    skip_frontend: bool,
    reset: bool,
) -> InstalledRecord:
    """Run dashboard dependency + frontend install and write .installed marker."""
    root = dashboard_root()

    if not skip_python:
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("`uv` not found. Install uv and retry `llm dashboard install`.")
        venv_python = _managed_venv_python(root)
        if venv_python is None:
            raise RuntimeError(
                f"managed venv not found at {root.parent / '.venv'}; rerun install.sh first."
            )
        subprocess.check_call(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(venv_python),
                "fastapi>=0.115,<1.0",
                "uvicorn[standard]>=0.30,<1.0",
                "sse-starlette>=2.1,<3.0",
            ]
        )

    if not skip_frontend:
        node_v = _probe_node_version()
        _check_node_minimum(node_v)
        npm_v = _probe_npm_version()
        if reset:
            shutil.rmtree(root / "node_modules", ignore_errors=True)
        subprocess.check_call(["npm", "ci"], cwd=root)
        subprocess.check_call(["npm", "run", "build"], cwd=root)
    else:
        try:
            node_v = _probe_node_version()
        except RuntimeError:
            node_v = "skipped"
        try:
            npm_v = _probe_npm_version()
        except RuntimeError:
            npm_v = "skipped"

    d = dist_dir()
    if not (d / "index.html").is_file():
        raise RuntimeError(
            "dashboard/dist/index.html missing. Run without --skip-frontend or build first."
        )

    record = InstalledRecord(
        installed_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        cli_version=cli_version,
        node_version=node_v,
        npm_version=npm_v,
        dist_hash=compute_dist_hash(d),
    )
    write_installed_record(record)
    return record
