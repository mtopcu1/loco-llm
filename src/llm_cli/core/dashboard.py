"""Dashboard install lifecycle helpers."""
from __future__ import annotations

import hashlib
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml

from llm_cli.core.lifecycle import state_dir, state_root
from llm_cli.core.scaffold import install_root
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
    """Install-root path to the dashboard/ source directory."""
    return install_root() / "dashboard"


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
    d = state_dir(state_root(settings)) / "dashboard"
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
            raise RuntimeError("`uv` not found. Install uv and retry `loco dashboard install`.")
        venv_python = _managed_venv_python(root)
        if venv_python is None:
            raise RuntimeError(
                f"managed venv not found at {root.parent / '.venv'}; rerun install.sh first."
            )
        install_root = root.parent
        subprocess.check_call(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(venv_python),
                "-e",
                f"{install_root}[dashboard]",
            ],
            cwd=str(install_root),
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


def _tail_log(path: Path, *, max_lines: int = 24) -> str:
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    return "\n".join(lines[-max_lines:])


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def _allowed_hosts_for(host: str, port: int) -> set[str]:
    return {
        f"{host}:{port}",
        f"localhost:{port}",
        f"127.0.0.1:{port}",
    }


def _write_security_log_line(
    host: str, port: int, *, allowed_hosts: set[str], insecure: bool
) -> None:
    log_path = server_log_path()
    with log_path.open("ab") as f:
        f.write(
            f"[SECURITY] Started with --insecure={insecure} on {host}:{port}; "
            f"allowed_hosts={sorted(allowed_hosts)}\n".encode()
        )


def _apply_server_env(
    env: dict[str, str], *, allowed_hosts: set[str], insecure: bool
) -> None:
    env["LLM_DASHBOARD_ALLOWED_HOSTS"] = ",".join(sorted(allowed_hosts))
    if insecure:
        env["LLM_DASHBOARD_INSECURE"] = "1"


def start_server_background(
    host: str,
    port: int,
    *,
    allowed_hosts: set[str] | None = None,
    insecure: bool = False,
) -> int:
    """Spawn uvicorn detached and wait until /api/health is ready."""
    if _port_in_use(host, port):
        raise RuntimeError(f"Port {port} already in use on {host}.")

    allowed_hosts = allowed_hosts or _allowed_hosts_for(host, port)
    _write_security_log_line(host, port, allowed_hosts=allowed_hosts, insecure=insecure)

    log_path = server_log_path()
    log_fd = log_path.open("ab")
    env = os.environ.copy()
    from llm_cli.core.scaffold import data_home, install_root

    env.setdefault("LOCO_HOME", str(data_home()))
    env.setdefault("LOCO_INSTALL", str(install_root()))
    _apply_server_env(env, allowed_hosts=allowed_hosts, insecure=insecure)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "llm_cli.webapi.app:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=log_fd,
        stderr=log_fd,
        stdin=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    server_pid_path().write_text(str(proc.pid), encoding="utf-8")
    log_fd.close()

    deadline = time.time() + 30.0
    last_err: str | None = None
    while time.time() < deadline:
        try:
            import httpx

            response = httpx.get(
                f"http://{host}:{port}/api/health",
                headers={"Host": f"{host}:{port}"},
                timeout=1.0,
            )
            if response.status_code == 200 and response.json().get("ok") is True:
                return proc.pid
            last_err = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)

        if proc.poll() is not None:
            tail = _tail_log(log_path)
            msg = (
                f"Dashboard server exited during startup (last error: {last_err}). "
                f"See {log_path} for details."
            )
            if tail:
                msg += f"\n--- log tail ---\n{tail}"
            raise RuntimeError(msg)
        time.sleep(0.25)

    proc.terminate()
    raise RuntimeError(
        f"Dashboard server did not become ready within 30s (last error: {last_err})."
    )


def run_server_foreground(
    host: str,
    port: int,
    *,
    allowed_hosts: set[str] | None = None,
    insecure: bool = False,
) -> None:
    """Run uvicorn in-process and clean up pid file on exit."""
    import uvicorn

    allowed_hosts = allowed_hosts or _allowed_hosts_for(host, port)
    _write_security_log_line(host, port, allowed_hosts=allowed_hosts, insecure=insecure)

    server_pid_path().write_text(str(os.getpid()), encoding="utf-8")
    _apply_server_env(os.environ, allowed_hosts=allowed_hosts, insecure=insecure)
    try:
        uvicorn.run(
            "llm_cli.webapi.app:create_app",
            factory=True,
            host=host,
            port=port,
            log_level="warning",
        )
    finally:
        try:
            server_pid_path().unlink()
        except FileNotFoundError:
            pass


def stop_server() -> bool:
    """Stop dashboard server by pid file. Returns True if stop attempted."""
    pid = read_server_pid()
    if pid is None:
        return False
    if not is_server_alive(pid):
        try:
            server_pid_path().unlink()
        except FileNotFoundError:
            pass
        return False

    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return False

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not is_server_alive(pid):
            break
        time.sleep(0.25)

    if is_server_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except (AttributeError, ProcessLookupError, PermissionError):
            pass

    try:
        server_pid_path().unlink()
    except FileNotFoundError:
        pass
    return True


def open_browser(host: str, port: int) -> None:
    try:
        webbrowser.open(f"http://{host}:{port}/")
    except Exception:  # noqa: BLE001
        pass
