# Lifecycle & Serve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `loco serve` (foreground / background / systemd), `loco stop`, `loco switch`, `loco status`, `loco logs`. Track a single running service in `state/running.json`. Manage one systemd unit (`~/.config/systemd/user/loco.service`) rewritten per config. Upgrade `stub-runtime` from "exit 1" to a real toy server so tests can drive the whole lifecycle end-to-end.

**Architecture:** Three new core modules — `lifecycle.py` (state + reconcile), `serve_spawn.py` (bash builders + readiness probe), `systemd_unit.py` (template + systemctl wrappers). Two new command modules — `commands/serve.py` (`serve`, `switch`) and `commands/lifecycle_cmds.py` (`stop`, `status`, `logs`). All long-lived subprocess work happens through bash inside WSL (existing `core/wsl.run_repo_bash` mechanism), but the lifecycle commands need finer-grained control than `run_repo_bash` offers, so spawn helpers go into `serve_spawn.py` and accept an injectable runner for test seams.

**Tech Stack:** Python 3.11+, Typer (CLI), Rich (output), pytest. POSIX bash inside WSL. Systemd user units (optional / gated tests). Standard-library `socket` for port probes and `subprocess` for spawn.

**Reference spec:** `docs/superpowers/specs/2026-05-17-lifecycle-and-serve.md`

**Runtime contract clarifications** (locked here; spec is silent on the exact env interface):

- The CLI invokes `runtimes/<rt>/serve.sh` (no positional args). All inputs are passed via env:
  - `LLM_CONFIG_ID` — config id string
  - `LLM_SERVE_HOST` — from `cfg.serve.host`
  - `LLM_SERVE_PORT` — from `cfg.serve.port`
  - Every key in `cfg.serve.env` (with `${data_root}` expanded), passed verbatim
  - Plus the existing `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE`
- `serve.sh` **must** end with `exec <real-server …>` so the script's PID becomes the server's PID. We rely on this for clean `kill -TERM <pid>` from `loco stop`.
- `healthcheck.sh` is invoked with the same env, exits `0` when the service is ready.

**Running tests:** all commands assume the LocalLLM venv on PATH. From WSL:

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/c/Private/Projects/LocalLLM
/home/$USER/llm/.cli-venv/bin/python -m pytest tests -q
```

Replace the venv path with whatever `./install.sh` produced for you (under `$LLM_DATA_ROOT/.cli-venv`).

---

## File Structure (locked at start of plan)

**Created:**

```
src/llm_cli/core/lifecycle.py             # Tasks 1-5
src/llm_cli/core/serve_spawn.py           # Tasks 6-10
src/llm_cli/core/systemd_unit.py          # Tasks 11-14
src/llm_cli/commands/serve.py             # Tasks 15-20
src/llm_cli/commands/lifecycle_cmds.py    # Tasks 21-23
runtimes/stub-runtime/stub-server.py      # Task 25
tests/unit/test_lifecycle.py              # Tasks 1-5
tests/unit/test_serve_spawn.py            # Tasks 6-10
tests/unit/test_systemd_unit.py           # Tasks 11-14
tests/integration/test_cli_serve.py       # Tasks 15-20
tests/integration/test_cli_lifecycle.py   # Tasks 21-23
tests/integration/test_cli_systemd.py     # Task 17 (gated)
docs/lifecycle.md                         # Task 27
```

**Modified:**

```
src/llm_cli/main.py                       # Task 24
src/llm_cli/core/doctor.py                # Task 32
runtimes/stub-runtime/serve.sh            # Task 25
runtimes/stub-runtime/healthcheck.sh      # Task 25
README.md                                 # Task 28
docs/repo-conventions.md                  # Task 29
docs/add-a-runtime.md                     # Task 30
docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md   # Task 31
```

**Already correct (verify, don't touch):**

```
.gitignore                                # Already lists state/running.json, state/history.jsonl, state/logs/
```

---

## Phase 1 — Lifecycle state primitives

### Task 1: Module skeleton + `LifecycleRecord` + path helpers

**Files:**
- Create: `src/llm_cli/core/lifecycle.py`
- Create: `tests/unit/test_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_lifecycle.py
"""Tests for state/running.json, state/history.jsonl, and reconcile helpers."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.lifecycle import (
    LifecycleRecord,
    history_path,
    logs_dir,
    running_path,
    state_dir,
)


def test_state_paths_are_under_repo(tmp_path: Path) -> None:
    repo = tmp_path
    assert state_dir(repo) == repo / "state"
    assert running_path(repo) == repo / "state" / "running.json"
    assert history_path(repo) == repo / "state" / "history.jsonl"
    assert logs_dir(repo) == repo / "state" / "logs"


def test_lifecycle_record_foreground_roundtrip() -> None:
    rec = LifecycleRecord(
        mode="foreground",
        config_id="cfg-a",
        port=8000,
        started_at="2026-05-17T16:00:00Z",
        pid=1234,
        log_path="state/logs/cfg-a.log",
    )
    assert rec.mode == "foreground"
    assert rec.unit is None


def test_lifecycle_record_systemd_roundtrip() -> None:
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=8000,
        started_at="2026-05-17T16:00:00Z",
        unit="loco.service",
    )
    assert rec.pid is None
    assert rec.log_path is None
    assert rec.unit == "loco.service"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: ImportError on `llm_cli.core.lifecycle`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/llm_cli/core/lifecycle.py
"""Runtime-lifecycle state: running.json, history.jsonl, PID liveness, reconcile."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LifecycleRecord:
    """In-memory shape of state/running.json. Exactly one record exists at a time."""

    mode: str  # "foreground" | "background" | "systemd"
    config_id: str
    port: int
    started_at: str  # ISO-8601 UTC, e.g. "2026-05-17T16:00:00Z"
    pid: int | None = None
    log_path: str | None = None  # repo-relative POSIX path; None for systemd
    unit: str | None = None  # "loco.service" for systemd; None otherwise


def state_dir(repo: Path) -> Path:
    return repo / "state"


def running_path(repo: Path) -> Path:
    return state_dir(repo) / "running.json"


def history_path(repo: Path) -> Path:
    return state_dir(repo) / "history.jsonl"


def logs_dir(repo: Path) -> Path:
    return state_dir(repo) / "logs"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(lifecycle): add module skeleton with state paths and record"
```

---

### Task 2: `read_running` / `write_running` / `clear_running`

**Files:**
- Modify: `src/llm_cli/core/lifecycle.py`
- Modify: `tests/unit/test_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lifecycle.py`:

```python
from llm_cli.core.lifecycle import (
    clear_running,
    read_running,
    write_running,
)


def test_read_running_missing_returns_none(tmp_path: Path) -> None:
    assert read_running(tmp_path) is None


def test_write_then_read_running(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=8000,
        started_at="2026-05-17T16:00:00Z",
        pid=1234,
        log_path="state/logs/cfg-a.log",
    )
    write_running(tmp_path, rec)
    got = read_running(tmp_path)
    assert got == rec


def test_write_running_creates_state_dir(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=1,
        started_at="t",
        pid=1,
        log_path="x",
    )
    write_running(tmp_path, rec)
    assert (tmp_path / "state" / "running.json").is_file()


def test_clear_running_is_idempotent(tmp_path: Path) -> None:
    clear_running(tmp_path)  # missing
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=1,
        started_at="t",
        unit="loco.service",
    )
    write_running(tmp_path, rec)
    clear_running(tmp_path)
    assert read_running(tmp_path) is None
    clear_running(tmp_path)  # already gone


def test_read_running_rejects_garbage(tmp_path: Path) -> None:
    path = tmp_path / "state" / "running.json"
    path.parent.mkdir()
    path.write_text("not json", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        read_running(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: ImportError on `read_running` / `write_running` / `clear_running`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/lifecycle.py`:

```python
import json
from dataclasses import asdict


def write_running(repo: Path, rec: LifecycleRecord) -> Path:
    """Atomically replace state/running.json with the given record."""
    sd = state_dir(repo)
    sd.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in asdict(rec).items() if v is not None}
    target = running_path(repo)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target


def read_running(repo: Path) -> LifecycleRecord | None:
    path = running_path(repo)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be an object")
    return LifecycleRecord(
        mode=str(raw["mode"]),
        config_id=str(raw["config_id"]),
        port=int(raw["port"]),
        started_at=str(raw["started_at"]),
        pid=int(raw["pid"]) if "pid" in raw else None,
        log_path=str(raw["log_path"]) if "log_path" in raw else None,
        unit=str(raw["unit"]) if "unit" in raw else None,
    )


def clear_running(repo: Path) -> None:
    path = running_path(repo)
    if path.is_file():
        path.unlink()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(lifecycle): read/write/clear running.json with atomic replace"
```

---

### Task 3: `append_history(event)` JSONL append

**Files:**
- Modify: `src/llm_cli/core/lifecycle.py`
- Modify: `tests/unit/test_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lifecycle.py`:

```python
import json as _json

from llm_cli.core.lifecycle import append_history


def test_append_history_creates_file_and_appends(tmp_path: Path) -> None:
    append_history(tmp_path, {"action": "start", "mode": "background"})
    append_history(tmp_path, {"action": "stop", "mode": "background"})
    lines = (tmp_path / "state" / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = _json.loads(lines[0])
    assert first["action"] == "start"
    assert "ts" in first  # auto-added timestamp


def test_append_history_does_not_overwrite_provided_ts(tmp_path: Path) -> None:
    append_history(tmp_path, {"ts": "fixed", "action": "x"})
    line = (tmp_path / "state" / "history.jsonl").read_text(encoding="utf-8").strip()
    assert _json.loads(line)["ts"] == "fixed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: ImportError on `append_history`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/lifecycle.py`:

```python
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_history(repo: Path, event: dict[str, Any]) -> None:
    """Append a JSON object as one line to state/history.jsonl."""
    sd = state_dir(repo)
    sd.mkdir(parents=True, exist_ok=True)
    line = dict(event)
    line.setdefault("ts", _utc_now_iso())
    with history_path(repo).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(lifecycle): append_history writes one JSON object per line"
```

---

### Task 4: `is_alive(pid)` cross-platform liveness probe

**Files:**
- Modify: `src/llm_cli/core/lifecycle.py`
- Modify: `tests/unit/test_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lifecycle.py`:

```python
import os

from llm_cli.core.lifecycle import is_alive


def test_is_alive_true_for_self() -> None:
    assert is_alive(os.getpid()) is True


def test_is_alive_false_for_invalid() -> None:
    # PID 0 is special everywhere; never a real process we own.
    assert is_alive(0) is False


def test_is_alive_false_for_dead_pid() -> None:
    # PID 999999 — likely outside the process table; if not, this is still a safe sentinel.
    assert is_alive(999_999) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: ImportError on `is_alive`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/lifecycle.py`:

```python
import os as _os


def is_alive(pid: int) -> bool:
    """Return True if pid identifies a live process owned by this user.

    POSIX: `kill(pid, 0)` raises ESRCH if dead, EPERM if alive-but-not-ours,
    or succeeds if alive-and-ours. We treat EPERM as alive (the process exists).

    Windows: best-effort `OpenProcess`; never expected in production
    (we always run lifecycle commands inside WSL), so a False return on
    Windows is fine.
    """
    if pid <= 0:
        return False
    if _os.name == "nt":
        return False
    try:
        _os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(lifecycle): is_alive(pid) probe with POSIX kill(0) semantics"
```

---

### Task 5: `reconcile()` — drop stale fg/bg records

**Files:**
- Modify: `src/llm_cli/core/lifecycle.py`
- Modify: `tests/unit/test_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lifecycle.py`:

```python
from unittest.mock import patch

from llm_cli.core.lifecycle import reconcile


def test_reconcile_keeps_live_pid(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=1,
        started_at="t",
        pid=os.getpid(),
        log_path="x",
    )
    write_running(tmp_path, rec)
    reconcile(tmp_path)
    assert read_running(tmp_path) == rec


def test_reconcile_drops_dead_pid(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="background",
        config_id="cfg-a",
        port=1,
        started_at="t",
        pid=999_999,
        log_path="x",
    )
    write_running(tmp_path, rec)
    reconcile(tmp_path)
    assert read_running(tmp_path) is None
    hist = (tmp_path / "state" / "history.jsonl").read_text(encoding="utf-8").strip()
    assert "reap-stale" in hist
    assert "cfg-a" in hist


def test_reconcile_drops_systemd_when_inactive(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=1,
        started_at="t",
        unit="loco.service",
    )
    write_running(tmp_path, rec)
    with patch("llm_cli.core.lifecycle._systemd_is_active", return_value=False):
        reconcile(tmp_path)
    assert read_running(tmp_path) is None


def test_reconcile_keeps_systemd_when_active(tmp_path: Path) -> None:
    rec = LifecycleRecord(
        mode="systemd",
        config_id="cfg-a",
        port=1,
        started_at="t",
        unit="loco.service",
    )
    write_running(tmp_path, rec)
    with patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True):
        reconcile(tmp_path)
    assert read_running(tmp_path) == rec


def test_reconcile_with_no_record_is_noop(tmp_path: Path) -> None:
    reconcile(tmp_path)
    assert read_running(tmp_path) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: ImportError on `reconcile`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/lifecycle.py`:

```python
import subprocess as _subprocess


def _systemd_is_active(unit: str) -> bool:
    """True if `systemctl --user is-active <unit>` prints 'active'."""
    try:
        r = _subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        return False
    return r.stdout.strip() == "active"


def reconcile(repo: Path) -> None:
    """Drop a stale record from running.json. Side-effect: history append on drop."""
    rec = read_running(repo)
    if rec is None:
        return
    if rec.mode in ("foreground", "background"):
        if rec.pid is None or not is_alive(rec.pid):
            append_history(
                repo,
                {
                    "action": "reap-stale",
                    "mode": rec.mode,
                    "config_id": rec.config_id,
                    "reason": "pid-gone",
                },
            )
            clear_running(repo)
        return
    if rec.mode == "systemd":
        if not rec.unit or not _systemd_is_active(rec.unit):
            append_history(
                repo,
                {
                    "action": "reap-stale",
                    "mode": "systemd",
                    "config_id": rec.config_id,
                    "reason": "unit-inactive",
                },
            )
            clear_running(repo)
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(lifecycle): reconcile drops stale fg/bg/systemd records"
```

---

## Phase 2 — Serve spawn helpers

### Task 6: `port_in_use(host, port)` probe

**Files:**
- Create: `src/llm_cli/core/serve_spawn.py`
- Create: `tests/unit/test_serve_spawn.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_serve_spawn.py
"""Tests for serve_spawn: bash builders, port probe, readiness loop."""
from __future__ import annotations

import socket

from llm_cli.core.serve_spawn import port_in_use


def test_port_in_use_false_on_free_port() -> None:
    # Find a free port by binding to :0 then closing.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert port_in_use("127.0.0.1", port) is False


def test_port_in_use_true_when_bound() -> None:
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen()
    try:
        assert port_in_use("127.0.0.1", port) is True
    finally:
        s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: ImportError on `port_in_use`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/llm_cli/core/serve_spawn.py
"""Build bash commands, probe ports, wait for readiness, spawn fg/bg processes."""
from __future__ import annotations

import socket


def port_in_use(host: str, port: int) -> bool:
    """True if attempting to bind (host, port) raises EADDRINUSE."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        try:
            s.bind((host, port))
        except OSError:
            return True
        return False
    finally:
        s.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/serve_spawn.py tests/unit/test_serve_spawn.py
git commit -m "feat(serve-spawn): port_in_use bind probe"
```

---

### Task 7: `build_serve_command(...)` bash builder

Produces the bash command string used by all spawn paths. Builds the `inner` script — the spawn helpers wrap it with `bash -lc` or `nohup … & echo $!` as needed.

**Files:**
- Modify: `src/llm_cli/core/serve_spawn.py`
- Modify: `tests/unit/test_serve_spawn.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_serve_spawn.py`:

```python
from llm_cli.core.serve_spawn import build_serve_inner


def test_build_serve_inner_uses_exec_and_cd() -> None:
    inner = build_serve_inner(
        repo_posix="/repo",
        script_posix_relpath="runtimes/stub/serve.sh",
    )
    assert inner.startswith("set -euo pipefail; ")
    assert "cd '/repo'" in inner
    assert inner.endswith("exec bash 'runtimes/stub/serve.sh'")


def test_build_serve_inner_quotes_paths_with_spaces() -> None:
    inner = build_serve_inner(
        repo_posix="/home/me/a repo",
        script_posix_relpath="runtimes/x/serve.sh",
    )
    assert "'/home/me/a repo'" in inner
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: ImportError on `build_serve_inner`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/serve_spawn.py`:

```python
import shlex


def build_serve_inner(repo_posix: str, script_posix_relpath: str) -> str:
    """Inner bash for serve.sh — cd into repo and exec the script.

    The final `exec` is essential: it makes the script's PID become the
    server's PID, so `kill -TERM <pid>` from `loco stop` reaches the server
    directly with no intermediate bash wrapper.
    """
    rel = script_posix_relpath.lstrip("/")
    return (
        "set -euo pipefail; "
        f"cd {shlex.quote(repo_posix)}; "
        f"exec bash {shlex.quote(rel)}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/serve_spawn.py tests/unit/test_serve_spawn.py
git commit -m "feat(serve-spawn): build_serve_inner with exec for clean signal delivery"
```

---

### Task 8: `wait_for_ready(probe, timeout_s)` with injectable probe

**Files:**
- Modify: `src/llm_cli/core/serve_spawn.py`
- Modify: `tests/unit/test_serve_spawn.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_serve_spawn.py`:

```python
from llm_cli.core.serve_spawn import wait_for_ready


def test_wait_for_ready_succeeds_on_first_call() -> None:
    calls = {"n": 0}

    def probe() -> bool:
        calls["n"] += 1
        return True

    ok = wait_for_ready(probe, timeout_s=5.0, poll_s=0.01)
    assert ok is True
    assert calls["n"] == 1


def test_wait_for_ready_succeeds_after_some_failures() -> None:
    calls = {"n": 0}

    def probe() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    ok = wait_for_ready(probe, timeout_s=5.0, poll_s=0.01)
    assert ok is True
    assert calls["n"] == 3


def test_wait_for_ready_times_out() -> None:
    def probe() -> bool:
        return False

    ok = wait_for_ready(probe, timeout_s=0.05, poll_s=0.02)
    assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: ImportError on `wait_for_ready`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/serve_spawn.py`:

```python
import time
from typing import Callable


def wait_for_ready(
    probe: Callable[[], bool], *, timeout_s: float, poll_s: float = 1.0
) -> bool:
    """Poll `probe()` until it returns True or `timeout_s` elapses.

    `probe` is called at least once before timeout is honored. Returns True
    on success, False on timeout. Probe exceptions propagate (caller's choice).
    """
    deadline = time.monotonic() + timeout_s
    while True:
        if probe():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/serve_spawn.py tests/unit/test_serve_spawn.py
git commit -m "feat(serve-spawn): wait_for_ready poll loop with injectable probe"
```

---

### Task 9: `spawn_background(...)` — nohup + `echo $!` PID capture

**Files:**
- Modify: `src/llm_cli/core/serve_spawn.py`
- Modify: `tests/unit/test_serve_spawn.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_serve_spawn.py`:

```python
from unittest.mock import MagicMock

from llm_cli.core.serve_spawn import spawn_background


def test_spawn_background_runs_nohup_and_returns_pid() -> None:
    runner = MagicMock()
    runner.return_value = MagicMock(stdout="12345\n", returncode=0)
    pid = spawn_background(
        inner="set -e; exec bash 'runtimes/x/serve.sh'",
        log_path="/repo/state/logs/x.log",
        env={"LLM_DATA_ROOT": "/root"},
        runner=runner,
    )
    assert pid == 12345
    assert runner.call_count == 1
    cmd = runner.call_args[0][0]
    assert cmd[0] == "bash"
    assert cmd[1] == "-lc"
    bash_script = cmd[2]
    assert "nohup" in bash_script
    assert ">> '/repo/state/logs/x.log'" in bash_script
    assert "echo \"$!\"" in bash_script
    passed_env = runner.call_args[1]["env"]
    assert passed_env["LLM_DATA_ROOT"] == "/root"


def test_spawn_background_raises_when_stdout_has_no_pid() -> None:
    runner = MagicMock()
    runner.return_value = MagicMock(stdout="", returncode=0)
    import pytest
    with pytest.raises(RuntimeError):
        spawn_background(
            inner="x",
            log_path="/repo/log",
            env={},
            runner=runner,
        )


def test_spawn_background_raises_on_nonzero_exit() -> None:
    runner = MagicMock()
    runner.return_value = MagicMock(stdout="999\n", returncode=2)
    import pytest
    with pytest.raises(RuntimeError):
        spawn_background(
            inner="x",
            log_path="/repo/log",
            env={},
            runner=runner,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: ImportError on `spawn_background`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/serve_spawn.py`:

```python
import subprocess
from typing import Mapping


def _default_runner(cmd, *, env):  # pragma: no cover - thin wrapper
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)


def spawn_background(
    *,
    inner: str,
    log_path: str,
    env: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess] = _default_runner,
) -> int:
    """Run `inner` detached, append output to `log_path`, return child PID.

    Uses the classic POSIX trick: `nohup bash -c '<inner>' < /dev/null >> LOG 2>&1 & echo $!`.
    The wrapper `bash -lc` exits immediately, leaving the nohup'd grandchild running.
    """
    bash_script = (
        f"nohup bash -c {shlex.quote(inner)} "
        f"</dev/null >> {shlex.quote(log_path)} 2>&1 & "
        f'echo "$!"; '
        "disown $! 2>/dev/null || true"
    )
    result = runner(["bash", "-lc", bash_script], env=dict(env))
    if result.returncode != 0:
        raise RuntimeError(
            f"background spawn failed (rc={result.returncode}): "
            f"{getattr(result, 'stderr', '')!r}"
        )
    out = (result.stdout or "").strip().splitlines()
    if not out:
        raise RuntimeError("background spawn produced no PID on stdout")
    try:
        return int(out[-1])
    except ValueError as exc:
        raise RuntimeError(f"background spawn stdout not a PID: {out!r}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/serve_spawn.py tests/unit/test_serve_spawn.py
git commit -m "feat(serve-spawn): spawn_background uses nohup + echo \$! for PID"
```

---

### Task 10: `spawn_foreground(...)` — blocking Popen with injectable runner

**Files:**
- Modify: `src/llm_cli/core/serve_spawn.py`
- Modify: `tests/unit/test_serve_spawn.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_serve_spawn.py`:

```python
from llm_cli.core.serve_spawn import spawn_foreground


def test_spawn_foreground_invokes_runner_and_returns_pid_and_exit_code() -> None:
    """Foreground returns (pid, exit_code) — on_started fires once PID is known."""
    started = {"pid": None}

    def on_started(pid: int) -> None:
        started["pid"] = pid

    class FakePopen:
        def __init__(self, cmd, *, env):
            self.cmd = cmd
            self.env = env
            self.pid = 4242

        def wait(self) -> int:
            return 0

    runner = lambda cmd, *, env: FakePopen(cmd, env=env)
    pid, code = spawn_foreground(
        inner="x",
        env={"LLM_DATA_ROOT": "/r"},
        on_started=on_started,
        runner=runner,
    )
    assert pid == 4242
    assert code == 0
    assert started["pid"] == 4242


def test_spawn_foreground_propagates_nonzero_exit() -> None:
    class FakePopen:
        pid = 99
        def __init__(self, cmd, *, env): pass
        def wait(self): return 7

    pid, code = spawn_foreground(
        inner="x",
        env={},
        on_started=lambda _pid: None,
        runner=lambda cmd, *, env: FakePopen(cmd, env=env),
    )
    assert code == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: ImportError on `spawn_foreground`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/serve_spawn.py`:

```python
def _default_popen(cmd, *, env):  # pragma: no cover - thin wrapper
    return subprocess.Popen(cmd, env=env)


def spawn_foreground(
    *,
    inner: str,
    env: Mapping[str, str],
    on_started: Callable[[int], None],
    runner: Callable[..., subprocess.Popen] = _default_popen,
) -> tuple[int, int]:
    """Run `inner` attached to the current terminal. Block until it exits.

    Calls `on_started(pid)` once the child is spawned (caller uses this to
    write state/running.json). Returns (pid, exit_code).
    """
    proc = runner(["bash", "-lc", inner], env=dict(env))
    on_started(proc.pid)
    return proc.pid, int(proc.wait())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serve_spawn.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/serve_spawn.py tests/unit/test_serve_spawn.py
git commit -m "feat(serve-spawn): spawn_foreground blocks with on_started callback"
```

---

## Phase 3 — Systemd unit module

### Task 11: `desired_unit_text(config_id)` template render

**Files:**
- Create: `src/llm_cli/core/systemd_unit.py`
- Create: `tests/unit/test_systemd_unit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_systemd_unit.py
"""Tests for systemd_unit: template, write-if-different, and systemctl wrappers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from llm_cli.core.systemd_unit import desired_unit_text


def test_desired_unit_text_contains_config_and_exec() -> None:
    txt = desired_unit_text("vllm-cuda__qwen2-7b-instruct__default")
    assert "AUTO-GENERATED" in txt
    assert "Description=LocalLLM service (config: vllm-cuda__qwen2-7b-instruct__default)" in txt
    assert "ExecStart=" in txt
    assert "vllm-cuda__qwen2-7b-instruct__default --foreground-from-supervisor" in txt
    assert "Restart=on-failure" in txt
    assert "WantedBy=default.target" in txt


def test_desired_unit_text_is_deterministic() -> None:
    assert desired_unit_text("a") == desired_unit_text("a")
    assert desired_unit_text("a") != desired_unit_text("b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: ImportError on `desired_unit_text`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/llm_cli/core/systemd_unit.py
"""Render and manage the single `loco.service` user unit."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

_UNIT_TEMPLATE = """\
# AUTO-GENERATED by `loco serve`. Edit will be overwritten on next `loco serve --systemd`.
[Unit]
Description=LocalLLM service (config: {config_id})
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/loco serve {config_id} --foreground-from-supervisor
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
"""


def desired_unit_text(config_id: str) -> str:
    return _UNIT_TEMPLATE.format(config_id=config_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/systemd_unit.py tests/unit/test_systemd_unit.py
git commit -m "feat(systemd): render loco.service template per config"
```

---

### Task 12: `unit_path()` honoring `$XDG_CONFIG_HOME`

**Files:**
- Modify: `src/llm_cli/core/systemd_unit.py`
- Modify: `tests/unit/test_systemd_unit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_systemd_unit.py`:

```python
from llm_cli.core.systemd_unit import unit_path


def test_unit_path_uses_xdg_config_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert unit_path() == tmp_path / "systemd" / "user" / "loco.service"


def test_unit_path_falls_back_to_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert unit_path() == tmp_path / ".config" / "systemd" / "user" / "loco.service"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: ImportError on `unit_path`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/systemd_unit.py`:

```python
def unit_path() -> Path:
    """Resolve ~/.config/systemd/user/loco.service honoring $XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "systemd" / "user" / "loco.service"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/systemd_unit.py tests/unit/test_systemd_unit.py
git commit -m "feat(systemd): unit_path resolves via XDG with HOME fallback"
```

---

### Task 13: `write_if_different(text)` — returns True only when bytes change

**Files:**
- Modify: `src/llm_cli/core/systemd_unit.py`
- Modify: `tests/unit/test_systemd_unit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_systemd_unit.py`:

```python
from llm_cli.core.systemd_unit import write_if_different


def test_write_if_different_creates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    changed = write_if_different("hello\n")
    assert changed is True
    assert unit_path().read_text(encoding="utf-8") == "hello\n"


def test_write_if_different_no_op_on_same_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_if_different("v1\n")
    changed = write_if_different("v1\n")
    assert changed is False


def test_write_if_different_replaces_on_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_if_different("v1\n")
    changed = write_if_different("v2\n")
    assert changed is True
    assert unit_path().read_text(encoding="utf-8") == "v2\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: ImportError on `write_if_different`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/systemd_unit.py`:

```python
def write_if_different(text: str) -> bool:
    """Write unit text to disk only if it differs. Returns True on change."""
    path = unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/systemd_unit.py tests/unit/test_systemd_unit.py
git commit -m "feat(systemd): write_if_different skips disk write when unchanged"
```

---

### Task 14: `systemctl` wrappers — `daemon_reload`, `restart_unit`, `stop_unit`, `is_active`

**Files:**
- Modify: `src/llm_cli/core/systemd_unit.py`
- Modify: `tests/unit/test_systemd_unit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_systemd_unit.py`:

```python
from llm_cli.core.systemd_unit import (
    daemon_reload,
    is_active,
    restart_unit,
    stop_unit,
)


def test_daemon_reload_calls_systemctl_user() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    daemon_reload(runner=runner)
    runner.assert_called_once()
    cmd = runner.call_args[0][0]
    assert cmd == ["systemctl", "--user", "daemon-reload"]


def test_restart_unit_calls_systemctl_restart() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    restart_unit("loco.service", runner=runner)
    cmd = runner.call_args[0][0]
    assert cmd == ["systemctl", "--user", "restart", "loco.service"]


def test_stop_unit_calls_systemctl_stop() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    stop_unit("loco.service", runner=runner)
    cmd = runner.call_args[0][0]
    assert cmd == ["systemctl", "--user", "stop", "loco.service"]


def test_is_active_true_when_stdout_active() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="active\n", stderr=""))
    assert is_active("loco.service", runner=runner) is True


def test_is_active_false_when_stdout_inactive() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=3, stdout="inactive\n", stderr=""))
    assert is_active("loco.service", runner=runner) is False


def test_is_active_false_when_systemctl_missing() -> None:
    def runner(cmd, **kw):
        raise FileNotFoundError("systemctl")
    assert is_active("loco.service", runner=runner) is False


def test_restart_unit_raises_on_nonzero() -> None:
    runner = MagicMock(return_value=MagicMock(returncode=2, stdout="", stderr="boom"))
    import pytest
    with pytest.raises(RuntimeError):
        restart_unit("loco.service", runner=runner)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: ImportError on `daemon_reload` / `restart_unit` / `stop_unit` / `is_active`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/core/systemd_unit.py`:

```python
import subprocess as _subprocess


def _default_runner(cmd, **kw):  # pragma: no cover - thin wrapper
    return _subprocess.run(cmd, capture_output=True, text=True, timeout=20, **kw)


def daemon_reload(*, runner: Callable = _default_runner) -> None:
    r = runner(["systemctl", "--user", "daemon-reload"])
    if r.returncode != 0:
        raise RuntimeError(f"daemon-reload failed (rc={r.returncode}): {r.stderr!r}")


def restart_unit(unit: str, *, runner: Callable = _default_runner) -> None:
    r = runner(["systemctl", "--user", "restart", unit])
    if r.returncode != 0:
        raise RuntimeError(f"restart {unit} failed (rc={r.returncode}): {r.stderr!r}")


def stop_unit(unit: str, *, runner: Callable = _default_runner) -> None:
    r = runner(["systemctl", "--user", "stop", unit])
    if r.returncode != 0:
        raise RuntimeError(f"stop {unit} failed (rc={r.returncode}): {r.stderr!r}")


def is_active(unit: str, *, runner: Callable = _default_runner) -> bool:
    try:
        r = runner(["systemctl", "--user", "is-active", unit])
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        return False
    return (r.stdout or "").strip() == "active"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_systemd_unit.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/systemd_unit.py tests/unit/test_systemd_unit.py
git commit -m "feat(systemd): wrappers for daemon-reload, restart, stop, is-active"
```

---

## Phase 4 — `serve` and `switch` commands

### Task 15: `loco serve <config>` — background mode (the default)

**Files:**
- Create: `src/llm_cli/commands/serve.py`
- Create: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_serve.py
"""Integration tests for `loco serve`, `loco switch`. Uses runner injection — no real bash."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _configure(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


def _make_repo(root: Path, port: int = 18080) -> Path:
    repo = root / "repo"
    repo.mkdir()
    rt = repo / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text("id: rt-a\n", encoding="utf-8")
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    md = repo / "models" / "md-a"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text("id: md-a\n", encoding="utf-8")
    (md / "pull.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (repo / "configs").mkdir()
    (repo / "configs" / "cfg-a.yaml").write_text(
        f"id: cfg-a\nruntime: rt-a\nmodel: md-a\nserve:\n  host: 127.0.0.1\n  port: {port}\n",
        encoding="utf-8",
    )
    return repo


def test_serve_background_writes_running_json_and_calls_spawn(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18091)
    _configure(tmp_path, repo)
    with patch("llm_cli.commands.serve.spawn_background", return_value=5555) as sb, \
         patch("llm_cli.commands.serve.wait_for_ready", return_value=True), \
         patch("llm_cli.commands.serve.port_in_use", return_value=False):
        result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    sb.assert_called_once()
    from llm_cli.core.lifecycle import read_running
    rec = read_running(repo)
    assert rec is not None
    assert rec.mode == "background"
    assert rec.config_id == "cfg-a"
    assert rec.pid == 5555
    assert rec.port == 18091


def test_serve_fails_when_port_in_use(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18092)
    _configure(tmp_path, repo)
    with patch("llm_cli.commands.serve.port_in_use", return_value=True):
        result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "already in use" in result.stdout.lower()


def test_serve_fails_when_unknown_config(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["serve", "nope"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "unknown config" in result.stdout.lower()


def test_serve_readiness_timeout_kills_child_and_clears_state(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18093)
    _configure(tmp_path, repo)
    killed = {"called": False}
    def fake_kill(pid, sig):
        killed["called"] = True
    with patch("llm_cli.commands.serve.spawn_background", return_value=8888), \
         patch("llm_cli.commands.serve.wait_for_ready", return_value=False), \
         patch("llm_cli.commands.serve.port_in_use", return_value=False), \
         patch("llm_cli.commands.serve.os.kill", new=fake_kill):
        result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "timed out" in result.stdout.lower() or "did not become ready" in result.stdout.lower()
    assert killed["called"] is True
    from llm_cli.core.lifecycle import read_running
    assert read_running(repo) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_serve.py -v`
Expected: ImportError on `llm_cli.commands.serve` (command not wired yet — but Typer raises `No such command 'serve'`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/llm_cli/commands/serve.py
"""`loco serve` and `loco switch` — start a service in fg/bg/systemd."""
from __future__ import annotations

import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core.lifecycle import (
    LifecycleRecord,
    append_history,
    clear_running,
    logs_dir,
    read_running,
    reconcile,
    write_running,
)
from llm_cli.core.repo import repo_root
from llm_cli.core.serve_spawn import (
    build_serve_inner,
    port_in_use,
    spawn_background,
    spawn_foreground,
    wait_for_ready,
)
from llm_cli.core.settings import Settings, load_settings, resolve
from llm_cli.core.wsl import to_wsl_path

console = Console()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_cfg(repo: Path, config_id: str):
    cfg = registry.get_config(repo, config_id)
    if cfg is None:
        console.print(f"[red]error:[/red] unknown config {config_id!r}")
        raise typer.Exit(code=1)
    errs = registry.validate_config(repo, cfg)
    if errs:
        for e in errs:
            console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)
    return cfg


def _serve_env(settings: Settings, cfg_data: dict[str, Any]) -> dict[str, str]:
    """Merge LLM_* baseline + cfg.serve.{host,port,env} into one env dict."""
    serve = cfg_data["serve"]
    env = {
        "LLM_DATA_ROOT": settings.data_root.as_posix(),
        "LLM_REPO_ROOT": settings.repo_root.as_posix(),
        "LLM_RUNTIMES": settings.runtimes_dir.as_posix(),
        "LLM_MODELS": settings.models_dir.as_posix(),
        "LLM_CACHE": settings.cache_dir.as_posix(),
        "LLM_CONFIG_ID": str(cfg_data["id"]),
        "LLM_SERVE_HOST": str(serve["host"]),
        "LLM_SERVE_PORT": str(serve["port"]),
    }
    user_env = serve.get("env") or {}
    if isinstance(user_env, dict):
        for k, v in user_env.items():
            env[str(k)] = str(v)
    merged = os.environ.copy()
    merged.update(env)
    return merged


def _readiness_timeout(cfg_data: dict[str, Any]) -> int:
    ready = cfg_data.get("readiness") or {}
    if isinstance(ready, dict):
        t = ready.get("timeout_seconds")
        if isinstance(t, int) and t > 0:
            return t
    return 600


def _make_healthcheck_probe(
    settings: Settings, runtime_id: str, env: dict[str, str]
) -> "callable":
    """Return a callable: bash runtimes/<rt>/healthcheck.sh -> True on exit 0."""
    import subprocess
    repo_posix = to_wsl_path(settings.repo_root)
    inner = build_serve_inner(
        repo_posix=repo_posix,
        script_posix_relpath=f"runtimes/{runtime_id}/healthcheck.sh",
    )

    def probe() -> bool:
        r = subprocess.run(
            ["bash", "-lc", inner],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode == 0

    return probe


def _do_background(
    settings: Settings, cfg, repo: Path, env: dict[str, str]
) -> None:
    serve = cfg.data["serve"]
    host = str(serve["host"])
    port = int(serve["port"])
    if port_in_use(host, port):
        console.print(f"[red]error:[/red] port {port} is already in use")
        raise typer.Exit(code=1)

    logs_dir(repo).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(repo) / f"{cfg.id}.log").as_posix()
    repo_posix = to_wsl_path(settings.repo_root)
    inner = build_serve_inner(
        repo_posix=repo_posix,
        script_posix_relpath=f"runtimes/{cfg.data['runtime']}/serve.sh",
    )
    pid = spawn_background(inner=inner, log_path=log_path, env=env)
    timeout = _readiness_timeout(cfg.data)
    probe = _make_healthcheck_probe(settings, str(cfg.data["runtime"]), env)
    if not wait_for_ready(probe, timeout_s=float(timeout), poll_s=1.0):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        console.print(
            f"[red]error:[/red] {cfg.id} did not become ready in {timeout}s; "
            f"see {log_path}"
        )
        raise typer.Exit(code=1)
    rec = LifecycleRecord(
        mode="background",
        config_id=cfg.id,
        port=port,
        started_at=_utc_now_iso(),
        pid=pid,
        log_path=(Path("state/logs") / f"{cfg.id}.log").as_posix(),
    )
    write_running(repo, rec)
    append_history(repo, {"action": "start", "mode": "background", "config_id": cfg.id})
    console.print(f"[green]running[/green] {cfg.id} (pid {pid}, port {port})")


def serve(
    config_id: str = typer.Argument(..., help="Config id to start."),
    foreground: bool = typer.Option(False, "--foreground", help="Run attached to this terminal."),
    systemd: bool = typer.Option(False, "--systemd", help="Bind loco.service to this config."),
    foreground_from_supervisor: bool = typer.Option(
        False, "--foreground-from-supervisor", hidden=True
    ),
) -> None:
    """Start a server for <config_id>."""
    if foreground and systemd:
        console.print("[red]error:[/red] --foreground and --systemd are mutually exclusive")
        raise typer.Exit(code=1)
    repo = repo_root()
    reconcile(repo)
    cfg = _resolve_cfg(repo, config_id)
    settings = resolve(load_settings())
    cfg_resolved = resolve_config_for_display(cfg, settings)
    cfg_for_env = registry.ConfigRecord(id=cfg.id, path=cfg.path, data=cfg_resolved)
    env = _serve_env(settings, cfg_for_env.data)

    existing = read_running(repo)
    if existing and existing.config_id == config_id and not foreground_from_supervisor:
        console.print(
            f"[red]error:[/red] {config_id} already running in {existing.mode}; "
            f"use `loco switch` to change config or `loco stop` first"
        )
        raise typer.Exit(code=1)
    if existing and not foreground_from_supervisor:
        console.print(
            f"[red]error:[/red] {existing.config_id} already running in {existing.mode}; "
            "stop it first or use `loco switch`"
        )
        raise typer.Exit(code=1)

    if foreground:
        _do_foreground(settings, cfg_for_env, repo, env, from_supervisor=False)
    elif foreground_from_supervisor:
        _do_foreground(settings, cfg_for_env, repo, env, from_supervisor=True)
    elif systemd:
        _do_systemd(settings, cfg_for_env, repo, env)
    else:
        _do_background(settings, cfg_for_env, repo, env)


def _do_foreground(settings, cfg, repo, env, *, from_supervisor: bool):
    raise NotImplementedError  # filled in by Task 16


def _do_systemd(settings, cfg, repo, env):
    raise NotImplementedError  # filled in by Task 17


def switch(config_id: str = typer.Argument(..., help="New config id.")) -> None:
    raise NotImplementedError  # filled in by Task 19
```

Wire into `main.py` minimally so Typer recognizes the command (full wiring in Task 24):

Add at the bottom of `src/llm_cli/main.py`:

```python
from llm_cli.commands.serve import serve as _serve
app.command("serve", help="Start a config in fg/bg/systemd mode.")(_serve)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_serve.py -v -k background or port_in_use or unknown_config or readiness_timeout`
Expected: 4 passed (those covered by Task 15).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/serve.py src/llm_cli/main.py tests/integration/test_cli_serve.py
git commit -m "feat(serve): loco serve <cfg> background mode + port/readiness checks"
```

---

### Task 16: `--foreground` mode

**Files:**
- Modify: `src/llm_cli/commands/serve.py`
- Modify: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_cli_serve.py`:

```python
def test_serve_foreground_writes_running_and_clears_on_exit(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18094)
    _configure(tmp_path, repo)

    captured = {"on_started": None}

    def fake_spawn_fg(*, inner, env, on_started, **kw):
        captured["on_started"] = on_started
        on_started(7777)
        # Verify running.json was written by on_started before we return.
        from llm_cli.core.lifecycle import read_running
        assert read_running(repo).pid == 7777
        return 7777, 0

    with patch("llm_cli.commands.serve.spawn_foreground", new=fake_spawn_fg), \
         patch("llm_cli.commands.serve.port_in_use", return_value=False):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--foreground"], catch_exceptions=False
        )
    assert result.exit_code == 0
    from llm_cli.core.lifecycle import read_running
    assert read_running(repo) is None  # cleared on exit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_serve.py::test_serve_foreground_writes_running_and_clears_on_exit -v`
Expected: NotImplementedError from `_do_foreground` stub.

- [ ] **Step 3: Write minimal implementation**

Replace `_do_foreground` stub in `src/llm_cli/commands/serve.py` with:

```python
def _do_foreground(
    settings: Settings,
    cfg,
    repo: Path,
    env: dict[str, str],
    *,
    from_supervisor: bool,
) -> None:
    serve_obj = cfg.data["serve"]
    host = str(serve_obj["host"])
    port = int(serve_obj["port"])
    if not from_supervisor and port_in_use(host, port):
        console.print(f"[red]error:[/red] port {port} is already in use")
        raise typer.Exit(code=1)

    repo_posix = to_wsl_path(settings.repo_root)
    if from_supervisor:
        # systemd captures stdout/stderr; no tee, no running.json mutation.
        inner = build_serve_inner(
            repo_posix=repo_posix,
            script_posix_relpath=f"runtimes/{cfg.data['runtime']}/serve.sh",
        )
        _, code = spawn_foreground(
            inner=inner, env=env, on_started=lambda _pid: None
        )
        raise typer.Exit(code=code)

    logs_dir(repo).mkdir(parents=True, exist_ok=True)
    log_path = (logs_dir(repo) / f"{cfg.id}.log").as_posix()
    # tee to log + terminal
    inner = (
        f"set -euo pipefail; cd {to_wsl_path(settings.repo_root)!r}; "
        f"exec bash 'runtimes/{cfg.data['runtime']}/serve.sh' "
        f"2>&1 | tee -a {log_path!r}"
    )

    def on_started(pid: int) -> None:
        rec = LifecycleRecord(
            mode="foreground",
            config_id=cfg.id,
            port=port,
            started_at=_utc_now_iso(),
            pid=pid,
            log_path=(Path("state/logs") / f"{cfg.id}.log").as_posix(),
        )
        write_running(repo, rec)
        append_history(repo, {"action": "start", "mode": "foreground", "config_id": cfg.id})

    try:
        _, code = spawn_foreground(inner=inner, env=env, on_started=on_started)
    finally:
        clear_running(repo)
        append_history(repo, {"action": "stop", "mode": "foreground", "config_id": cfg.id})
    raise typer.Exit(code=code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_serve.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/serve.py tests/integration/test_cli_serve.py
git commit -m "feat(serve): --foreground tees to log, writes running.json, clears on exit"
```

---

### Task 17: `--systemd` mode + gated test

**Files:**
- Modify: `src/llm_cli/commands/serve.py`
- Modify: `tests/integration/test_cli_serve.py`
- Create: `tests/integration/test_cli_systemd.py`

- [ ] **Step 1: Write the failing test (mocked path, in test_cli_serve.py)**

Append to `tests/integration/test_cli_serve.py`:

```python
def test_serve_systemd_rewrites_unit_and_writes_running(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18095)
    _configure(tmp_path, repo)
    with patch("llm_cli.commands.serve.write_if_different", return_value=True) as wid, \
         patch("llm_cli.commands.serve.daemon_reload") as dr, \
         patch("llm_cli.commands.serve.restart_unit") as ru, \
         patch("llm_cli.commands.serve.wait_for_ready", return_value=True), \
         patch("llm_cli.commands.serve.systemd_is_active", return_value=True), \
         patch("llm_cli.commands.serve.port_in_use", return_value=False):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--systemd"], catch_exceptions=False
        )
    assert result.exit_code == 0, result.stdout
    wid.assert_called_once()
    dr.assert_called_once()
    ru.assert_called_once_with("loco.service")
    from llm_cli.core.lifecycle import read_running
    rec = read_running(repo)
    assert rec.mode == "systemd"
    assert rec.unit == "loco.service"
    assert rec.config_id == "cfg-a"


def test_serve_systemd_skips_daemon_reload_when_unit_unchanged(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18096)
    _configure(tmp_path, repo)
    with patch("llm_cli.commands.serve.write_if_different", return_value=False), \
         patch("llm_cli.commands.serve.daemon_reload") as dr, \
         patch("llm_cli.commands.serve.restart_unit") as ru, \
         patch("llm_cli.commands.serve.wait_for_ready", return_value=True), \
         patch("llm_cli.commands.serve.systemd_is_active", return_value=True), \
         patch("llm_cli.commands.serve.port_in_use", return_value=False):
        result = runner.invoke(
            app, ["serve", "cfg-a", "--systemd"], catch_exceptions=False
        )
    assert result.exit_code == 0
    dr.assert_not_called()
    ru.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_serve.py -k systemd -v`
Expected: NotImplementedError from `_do_systemd` stub (or AttributeError on `systemd_is_active` import).

- [ ] **Step 3: Write minimal implementation**

In `src/llm_cli/commands/serve.py`, add imports near the top:

```python
from llm_cli.core.systemd_unit import (
    daemon_reload,
    desired_unit_text,
    is_active as systemd_is_active,
    restart_unit,
    stop_unit,
    write_if_different,
)
```

Replace `_do_systemd` stub with:

```python
def _do_systemd(
    settings: Settings, cfg, repo: Path, env: dict[str, str]
) -> None:
    serve_obj = cfg.data["serve"]
    host = str(serve_obj["host"])
    port = int(serve_obj["port"])
    if port_in_use(host, port):
        console.print(f"[red]error:[/red] port {port} is already in use")
        raise typer.Exit(code=1)

    text = desired_unit_text(cfg.id)
    changed = write_if_different(text)
    append_history(
        repo,
        {"action": "systemd-write", "unit": "loco.service", "config_id": cfg.id, "changed": changed},
    )
    if changed:
        daemon_reload()
    restart_unit("loco.service")

    timeout = _readiness_timeout(cfg.data)
    probe = _make_healthcheck_probe(settings, str(cfg.data["runtime"]), env)

    def combined_probe() -> bool:
        return systemd_is_active("loco.service") and probe()

    if not wait_for_ready(combined_probe, timeout_s=float(timeout), poll_s=1.0):
        try:
            stop_unit("loco.service")
        except RuntimeError:
            pass
        console.print(
            f"[red]error:[/red] {cfg.id} did not become ready in {timeout}s; "
            f"see `journalctl --user -u loco.service -n 50`"
        )
        raise typer.Exit(code=1)
    rec = LifecycleRecord(
        mode="systemd",
        config_id=cfg.id,
        port=port,
        started_at=_utc_now_iso(),
        unit="loco.service",
    )
    write_running(repo, rec)
    append_history(repo, {"action": "start", "mode": "systemd", "config_id": cfg.id})
    console.print(f"[green]running[/green] {cfg.id} via systemd (port {port})")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_serve.py -v`
Expected: 7 passed.

- [ ] **Step 5: Create the gated real-systemd marker file**

Create `tests/integration/test_cli_systemd.py`:

```python
"""Real-systemd integration tests. Gated: skip unless `systemctl --user` works."""
from __future__ import annotations

import shutil
import subprocess

import pytest


def _systemd_user_available() -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        r = subprocess.run(
            ["systemctl", "--user", "list-units", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0


pytestmark = pytest.mark.skipif(
    not _systemd_user_available(),
    reason="systemctl --user not available (CI default)",
)


def test_real_systemd_smoke_placeholder() -> None:
    # Real flow is exercised manually via README smoke. This module exists so
    # the marker is wired and CI sees a skip rather than a missing file.
    assert _systemd_user_available()
```

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/commands/serve.py tests/integration/test_cli_serve.py tests/integration/test_cli_systemd.py
git commit -m "feat(serve): --systemd rewrites unit, reloads only on change, waits"
```

---

### Task 18: `--foreground-from-supervisor` end-to-end sanity

Already implemented in Task 16 (the `from_supervisor=True` branch). Add a focused test that confirms it does **not** write `running.json` and is hidden from `--help`.

**Files:**
- Modify: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_cli_serve.py`:

```python
def test_foreground_from_supervisor_does_not_touch_running_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18097)
    _configure(tmp_path, repo)
    # Pre-write a running.json as if --systemd parent did so.
    from llm_cli.core.lifecycle import LifecycleRecord, write_running, read_running
    pre = LifecycleRecord(
        mode="systemd", config_id="cfg-a", port=18097,
        started_at="t", unit="loco.service",
    )
    write_running(repo, pre)

    def fake_spawn_fg(*, inner, env, on_started, **kw):
        on_started(1234)  # but supervisor branch should pass a no-op callback
        return 1234, 0

    # Stop reconcile() from reaping the systemd record we just wrote.
    with patch("llm_cli.commands.serve.spawn_foreground", new=fake_spawn_fg), \
         patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True):
        # NB: --foreground-from-supervisor is hidden but accepted.
        result = runner.invoke(
            app, ["serve", "cfg-a", "--foreground-from-supervisor"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    # running.json should still equal the systemd record we wrote.
    assert read_running(repo) == pre


def test_foreground_from_supervisor_hidden_from_help() -> None:
    result = runner.invoke(app, ["serve", "--help"], catch_exceptions=False)
    assert "--foreground-from-supervisor" not in result.stdout
```

- [ ] **Step 2: Run test to verify**

Run: `pytest tests/integration/test_cli_serve.py -k supervisor -v`
Expected: 2 passed. (Implementation already exists from Task 16; conflict check in Task 15 must NOT trip on supervisor flag — verify the `if existing ...` guard skips when `foreground_from_supervisor` is True.)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_cli_serve.py
git commit -m "test(serve): supervisor mode preserves running.json and is hidden"
```

---

### Task 19: `loco switch <config>` — stop + start same mode

**Files:**
- Modify: `src/llm_cli/commands/serve.py`
- Modify: `src/llm_cli/main.py`
- Modify: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_cli_serve.py`:

```python
def test_switch_background_stops_old_starts_new(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18098)
    _configure(tmp_path, repo)
    # Pre-write a bg running.json for cfg-a with self PID so reconcile keeps it.
    import os
    from llm_cli.core.lifecycle import LifecycleRecord, write_running
    write_running(
        repo,
        LifecycleRecord(
            mode="background", config_id="cfg-a", port=18098,
            started_at="t", pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    # Add a second config cfg-b on a different port.
    (repo / "configs" / "cfg-b.yaml").write_text(
        "id: cfg-b\nruntime: rt-a\nmodel: md-a\n"
        "serve:\n  host: 127.0.0.1\n  port: 18099\n",
        encoding="utf-8",
    )
    killed = {"pid": None, "sig": None}
    def fake_kill(pid, sig):
        killed["pid"] = pid
        killed["sig"] = sig
    with patch("llm_cli.commands.serve.os.kill", new=fake_kill), \
         patch("llm_cli.commands.serve.spawn_background", return_value=5151), \
         patch("llm_cli.commands.serve.wait_for_ready", return_value=True), \
         patch("llm_cli.commands.serve.port_in_use", return_value=False), \
         patch("llm_cli.commands.serve._wait_pid_gone", return_value=True):
        result = runner.invoke(app, ["switch", "cfg-b"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    assert killed["pid"] == os.getpid()
    from llm_cli.core.lifecycle import read_running
    rec = read_running(repo)
    assert rec.config_id == "cfg-b"
    assert rec.mode == "background"


def test_switch_errors_when_nothing_running(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["switch", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "nothing running" in result.stdout.lower()


def test_switch_foreground_refuses_with_hint(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    import os
    from llm_cli.core.lifecycle import LifecycleRecord, write_running
    write_running(
        repo,
        LifecycleRecord(
            mode="foreground", config_id="cfg-a", port=1,
            started_at="t", pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    result = runner.invoke(app, ["switch", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "foreground" in result.stdout.lower()
    assert "ctrl" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_serve.py -k switch -v`
Expected: NotImplementedError from `switch` stub.

- [ ] **Step 3: Write minimal implementation**

In `src/llm_cli/commands/serve.py`, add a helper near the bottom:

```python
def _wait_pid_gone(pid: int, timeout_s: float = 10.0, poll_s: float = 0.2) -> bool:
    """Poll until is_alive(pid) is False or timeout elapses. Returns True if gone."""
    from llm_cli.core.lifecycle import is_alive
    deadline = time.monotonic() + timeout_s
    while is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)
    return True
```

Replace the `switch` stub with:

```python
def switch(config_id: str = typer.Argument(..., help="New config id.")) -> None:
    """Stop the currently-running service and start <config_id> in the same mode."""
    repo = repo_root()
    reconcile(repo)
    rec = read_running(repo)
    if rec is None:
        console.print(
            f"[red]error:[/red] nothing running; "
            f"use `loco serve {config_id}` instead"
        )
        raise typer.Exit(code=1)
    if rec.mode == "foreground":
        console.print(
            "[red]error:[/red] foreground sessions can't be switched; "
            "Ctrl-C in the original terminal and rerun `loco serve <new>`"
        )
        raise typer.Exit(code=1)

    settings = resolve(load_settings())
    new_cfg = _resolve_cfg(repo, config_id)
    cfg_resolved = resolve_config_for_display(new_cfg, settings)
    new_for_env = registry.ConfigRecord(id=new_cfg.id, path=new_cfg.path, data=cfg_resolved)
    env = _serve_env(settings, new_for_env.data)
    old_mode = rec.mode
    old_id = rec.config_id

    if rec.mode == "background":
        if rec.pid is None:
            console.print("[red]error:[/red] running record has no pid; aborting switch")
            raise typer.Exit(code=1)
        try:
            os.kill(rec.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_pid_gone(rec.pid, timeout_s=10.0):
            try:
                os.kill(rec.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        clear_running(repo)
        append_history(
            repo,
            {"action": "switch", "mode": "background", "from": old_id, "to": config_id},
        )
        _do_background(settings, new_for_env, repo, env)
        return

    if rec.mode == "systemd":
        clear_running(repo)
        append_history(
            repo,
            {"action": "switch", "mode": "systemd", "from": old_id, "to": config_id},
        )
        _do_systemd(settings, new_for_env, repo, env)
        return

    console.print(f"[red]error:[/red] unknown mode {rec.mode!r}")
    raise typer.Exit(code=1)
```

Wire into `main.py`:

```python
from llm_cli.commands.serve import switch as _switch
app.command("switch", help="Stop the current service and start a new config in the same mode.")(_switch)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_serve.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/serve.py src/llm_cli/main.py tests/integration/test_cli_serve.py
git commit -m "feat(serve): loco switch <cfg> stops current and starts new in same mode"
```

---

### Task 20: `loco serve --systemd` idempotency on same unit text

When the desired unit text is byte-identical to disk **and** `systemd_is_active` is True **and** the existing record points at the same config, treat it as a no-op success. Already part of the conflict guard for the "same config running" case in Task 15; verify by adding a focused test.

**Files:**
- Modify: `src/llm_cli/commands/serve.py`
- Modify: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_cli_serve.py`:

```python
def test_serve_systemd_noop_when_same_config_already_active(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18100)
    _configure(tmp_path, repo)
    from llm_cli.core.lifecycle import LifecycleRecord, write_running
    write_running(
        repo,
        LifecycleRecord(
            mode="systemd", config_id="cfg-a", port=18100,
            started_at="t", unit="loco.service",
        ),
    )
    # Also patch the lifecycle-module copy so reconcile() doesn't reap the record.
    with patch("llm_cli.commands.serve.systemd_is_active", return_value=True), \
         patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True), \
         patch("llm_cli.commands.serve.write_if_different", return_value=False) as wid, \
         patch("llm_cli.commands.serve.restart_unit") as ru:
        result = runner.invoke(
            app, ["serve", "cfg-a", "--systemd"], catch_exceptions=False
        )
    # Expected: graceful "already serving" no-op.
    assert result.exit_code == 0, result.stdout
    assert "already serving" in result.stdout.lower()
    ru.assert_not_called()
    wid.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_serve.py::test_serve_systemd_noop_when_same_config_already_active -v`
Expected: FAIL — current code rejects on the conflict guard before reaching the no-op check.

- [ ] **Step 3: Write minimal implementation**

In `serve()` in `src/llm_cli/commands/serve.py`, **before** the conflict guard, add an early-return for the systemd-noop case:

```python
    if (
        systemd
        and existing is not None
        and existing.mode == "systemd"
        and existing.config_id == config_id
        and systemd_is_active("loco.service")
    ):
        console.print(f"[green]already serving[/green] {config_id} via systemd")
        return
```

(Place this right after `existing = read_running(repo)` and before the `if existing and existing.config_id == config_id` block. The early return short-circuits the conflict check.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_serve.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/serve.py tests/integration/test_cli_serve.py
git commit -m "feat(serve): --systemd is a no-op when same config already active"
```

---

## Phase 5 — `stop`, `status`, `logs`

### Task 21: `loco stop` (idempotent; fg/bg via SIGTERM; systemd via systemctl)

**Files:**
- Create: `src/llm_cli/commands/lifecycle_cmds.py`
- Create: `tests/integration/test_cli_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_lifecycle.py
"""Integration tests for `loco stop`, `loco status`, `loco logs`."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.lifecycle import (
    LifecycleRecord,
    logs_dir,
    read_running,
    write_running,
)
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _configure(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


def _empty_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    return repo


def test_stop_no_record_is_idempotent(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "nothing running" in result.stdout.lower()


def test_stop_background_sigterms_pid_and_clears(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="background", config_id="cfg-a", port=1,
            started_at="t", pid=os.getpid(),  # alive
            log_path="state/logs/cfg-a.log",
        ),
    )
    killed = {"pid": None, "sig": None}
    def fake_kill(pid, sig):
        killed["pid"] = pid
        killed["sig"] = sig
    with patch("llm_cli.commands.lifecycle_cmds.os.kill", new=fake_kill), \
         patch("llm_cli.commands.lifecycle_cmds._wait_pid_gone", return_value=True):
        result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    assert killed["pid"] == os.getpid()
    assert read_running(repo) is None


def test_stop_background_escalates_to_sigkill_if_pid_persists(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="background", config_id="cfg-a", port=1,
            started_at="t", pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    sigs = []
    def fake_kill(pid, sig):
        sigs.append(sig)
    with patch("llm_cli.commands.lifecycle_cmds.os.kill", new=fake_kill), \
         patch("llm_cli.commands.lifecycle_cmds._wait_pid_gone", side_effect=[False, True]):
        result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    import signal
    assert signal.SIGTERM in sigs
    assert signal.SIGKILL in sigs


def test_stop_systemd_calls_systemctl_stop(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="systemd", config_id="cfg-a", port=1,
            started_at="t", unit="loco.service",
        ),
    )
    # Patch lifecycle._systemd_is_active so reconcile() keeps the record.
    with patch("llm_cli.commands.lifecycle_cmds.stop_unit") as su, \
         patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True):
        result = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result.exit_code == 0
    su.assert_called_once_with("loco.service")
    assert read_running(repo) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_lifecycle.py -v`
Expected: No `stop` command registered → Typer error.

- [ ] **Step 3: Write minimal implementation**

```python
# src/llm_cli/commands/lifecycle_cmds.py
"""`loco stop`, `loco status`, `loco logs`."""
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.lifecycle import (
    append_history,
    clear_running,
    is_alive,
    read_running,
    reconcile,
)
from llm_cli.core.repo import repo_root
from llm_cli.core.systemd_unit import stop_unit

console = Console()


def _wait_pid_gone(pid: int, timeout_s: float = 10.0, poll_s: float = 0.2) -> bool:
    deadline = time.monotonic() + timeout_s
    while is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)
    return True


def stop() -> None:
    """Stop whatever is running (idempotent)."""
    repo = repo_root()
    reconcile(repo)
    rec = read_running(repo)
    if rec is None:
        console.print("nothing running")
        return
    if rec.mode in ("foreground", "background"):
        if rec.pid is None:
            clear_running(repo)
            console.print("cleared stale record (no pid)")
            return
        try:
            os.kill(rec.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_pid_gone(rec.pid, timeout_s=10.0):
            try:
                os.kill(rec.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _wait_pid_gone(rec.pid, timeout_s=2.0)
        clear_running(repo)
        append_history(repo, {"action": "stop", "mode": rec.mode, "config_id": rec.config_id})
        console.print(f"[green]stopped[/green] {rec.config_id}")
        return
    if rec.mode == "systemd":
        try:
            stop_unit("loco.service")
        except RuntimeError as exc:
            console.print(f"[yellow]warning:[/yellow] systemctl stop failed: {exc}")
        clear_running(repo)
        append_history(repo, {"action": "stop", "mode": "systemd", "config_id": rec.config_id})
        console.print(f"[green]stopped[/green] {rec.config_id} (systemd)")
        return
    console.print(f"[red]error:[/red] unknown mode {rec.mode!r}")
    raise typer.Exit(code=1)
```

Wire into `main.py`:

```python
from llm_cli.commands.lifecycle_cmds import stop as _stop
app.command("stop", help="Stop the currently-running service.")(_stop)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_lifecycle.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/lifecycle_cmds.py src/llm_cli/main.py tests/integration/test_cli_lifecycle.py
git commit -m "feat(lifecycle): loco stop with SIGTERM->SIGKILL escalation + systemd path"
```

---

### Task 22: `loco status` (text + `--json`)

**Files:**
- Modify: `src/llm_cli/commands/lifecycle_cmds.py`
- Modify: `src/llm_cli/main.py`
- Modify: `tests/integration/test_cli_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_cli_lifecycle.py`:

```python
import json as _json


def test_status_not_running(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["status"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "not running" in result.stdout.lower()


def test_status_background_text(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="background", config_id="cfg-a", port=18080,
            started_at="2026-05-17T16:00:00Z", pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    result = runner.invoke(app, ["status"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "running" in result.stdout.lower()
    assert "cfg-a" in result.stdout
    assert "18080" in result.stdout
    assert str(os.getpid()) in result.stdout


def test_status_json_includes_uptime_and_pid_alive(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="background", config_id="cfg-a", port=18080,
            started_at="2026-05-17T16:00:00Z", pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    result = runner.invoke(app, ["status", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    payload = _json.loads(result.stdout)
    assert payload["mode"] == "background"
    assert payload["config_id"] == "cfg-a"
    assert payload["pid"] == os.getpid()
    assert "uptime_seconds" in payload
    assert payload["pid_alive"] is True


def test_status_systemd_text(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="systemd", config_id="cfg-a", port=18080,
            started_at="2026-05-17T16:00:00Z", unit="loco.service",
        ),
    )
    # reconcile() inside status() must not reap the record.
    with patch("llm_cli.commands.lifecycle_cmds.systemd_is_active", return_value=True), \
         patch("llm_cli.core.lifecycle._systemd_is_active", return_value=True):
        result = runner.invoke(app, ["status"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "running" in result.stdout.lower()
    assert "loco.service" in result.stdout
    assert "journalctl" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_lifecycle.py -k status -v`
Expected: No `status` command registered.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/commands/lifecycle_cmds.py`:

```python
import json
from datetime import datetime, timezone

from llm_cli.core.systemd_unit import is_active as systemd_is_active


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _format_uptime(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def status(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
) -> None:
    """Print what's running. Always exits 0."""
    repo = repo_root()
    reconcile(repo)
    rec = read_running(repo)
    if rec is None:
        if as_json:
            typer.echo(json.dumps({"running": False}))
            return
        console.print("status: not running")
        return

    started = _parse_iso(rec.started_at)
    uptime_s = (
        int((datetime.now(timezone.utc) - started).total_seconds())
        if started else 0
    )
    pid_alive = is_alive(rec.pid) if rec.pid is not None else None

    if as_json:
        payload = {
            "running": True,
            "mode": rec.mode,
            "config_id": rec.config_id,
            "port": rec.port,
            "started_at": rec.started_at,
            "uptime_seconds": uptime_s,
        }
        if rec.pid is not None:
            payload["pid"] = rec.pid
            payload["pid_alive"] = bool(pid_alive)
        if rec.log_path is not None:
            payload["log_path"] = rec.log_path
        if rec.unit is not None:
            payload["unit"] = rec.unit
            payload["systemd_active"] = systemd_is_active(rec.unit)
        typer.echo(json.dumps(payload, indent=2))
        return

    console.print("status: running")
    console.print(f"mode:   {rec.mode}")
    console.print(f"config: {rec.config_id}")
    console.print(f"port:   {rec.port}")
    if rec.mode == "systemd":
        console.print(f"unit:   {rec.unit}")
        console.print(f"journalctl: journalctl --user -u {rec.unit}")
    else:
        console.print(f"pid:    {rec.pid}")
        console.print(f"log:    {rec.log_path}")
    console.print(f"uptime: {_format_uptime(uptime_s)}")
```

Wire into `main.py`:

```python
from llm_cli.commands.lifecycle_cmds import status as _status
app.command("status", help="Show what's currently running.")(_status)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_lifecycle.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/lifecycle_cmds.py src/llm_cli/main.py tests/integration/test_cli_lifecycle.py
git commit -m "feat(lifecycle): loco status (text + --json) with uptime and liveness"
```

---

### Task 23: `loco logs [-f] [-n N]`

**Files:**
- Modify: `src/llm_cli/commands/lifecycle_cmds.py`
- Modify: `src/llm_cli/main.py`
- Modify: `tests/integration/test_cli_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_cli_lifecycle.py`:

```python
def test_logs_no_record_errors(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["logs"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "nothing running" in result.stdout.lower()


def test_logs_background_tails_last_n_lines(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    logs_dir(repo).mkdir(parents=True, exist_ok=True)
    log = logs_dir(repo) / "cfg-a.log"
    log.write_text("\n".join(f"line-{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    write_running(
        repo,
        LifecycleRecord(
            mode="background", config_id="cfg-a", port=1,
            started_at="t", pid=os.getpid(),
            log_path="state/logs/cfg-a.log",
        ),
    )
    result = runner.invoke(app, ["logs", "-n", "5"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "line-20" in result.stdout
    assert "line-16" in result.stdout
    assert "line-15" not in result.stdout


def test_logs_systemd_invokes_journalctl(tmp_path: Path) -> None:
    repo = _empty_repo(tmp_path)
    _configure(tmp_path, repo)
    write_running(
        repo,
        LifecycleRecord(
            mode="systemd", config_id="cfg-a", port=1,
            started_at="t", unit="loco.service",
        ),
    )
    with patch("llm_cli.commands.lifecycle_cmds.subprocess.call", return_value=0) as call:
        result = runner.invoke(app, ["logs", "-n", "20"], catch_exceptions=False)
    assert result.exit_code == 0
    cmd = call.call_args[0][0]
    assert cmd[:3] == ["journalctl", "--user", "-u"]
    assert "loco.service" in cmd
    assert "-n" in cmd and "20" in cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_lifecycle.py -k logs -v`
Expected: No `logs` command registered.

- [ ] **Step 3: Write minimal implementation**

Append to `src/llm_cli/commands/lifecycle_cmds.py`:

```python
import subprocess


def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow appends."),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of trailing lines."),
) -> None:
    """Tail the log of the currently-running service."""
    repo = repo_root()
    reconcile(repo)
    rec = read_running(repo)
    if rec is None:
        console.print("nothing running")
        raise typer.Exit(code=1)
    if rec.mode == "systemd":
        cmd = ["journalctl", "--user", "-u", rec.unit or "loco.service", "-n", str(lines)]
        if follow:
            cmd.append("-f")
        raise typer.Exit(code=subprocess.call(cmd))
    if rec.log_path is None:
        console.print("[red]error:[/red] running record has no log_path")
        raise typer.Exit(code=1)
    log_file = (repo / rec.log_path).resolve()
    if not log_file.is_file():
        console.print(f"[yellow]warning:[/yellow] log file missing: {log_file}")
        raise typer.Exit(code=0)
    cmd = ["tail", "-n", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(str(log_file))
    raise typer.Exit(code=subprocess.call(cmd))
```

Wire into `main.py`:

```python
from llm_cli.commands.lifecycle_cmds import logs as _logs
app.command("logs", help="Tail logs of the currently-running service.")(_logs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_lifecycle.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/lifecycle_cmds.py src/llm_cli/main.py tests/integration/test_cli_lifecycle.py
git commit -m "feat(lifecycle): loco logs reads file (fg/bg) or journalctl (systemd)"
```

---

## Phase 6 — Stub-runtime upgrade + final wiring

### Task 24: Tidy `main.py` wiring

The earlier tasks each appended one-liners to `main.py`. Consolidate them into a single tidy block matching the existing style.

**Files:**
- Modify: `src/llm_cli/main.py`

- [ ] **Step 1: Inspect current state**

Run: `cat src/llm_cli/main.py` and verify all serve / switch / stop / status / logs lines exist.

- [ ] **Step 2: Reformat the bottom of `main.py`**

Replace the scattered `app.command(...)` lines added by Tasks 15/19/21/22/23 with a single grouped block immediately under the existing `build`/`pull` lines:

```python
# Lifecycle commands (serve, switch, stop, status, logs).
from llm_cli.commands import serve as serve_cmd
from llm_cli.commands import lifecycle_cmds

app.command("serve", help="Start a config in fg/bg/systemd mode.")(serve_cmd.serve)
app.command(
    "switch",
    help="Stop the current service and start a new config in the same mode.",
)(serve_cmd.switch)
app.command("stop", help="Stop the currently-running service.")(
    lifecycle_cmds.stop
)
app.command("status", help="Show what's currently running.")(lifecycle_cmds.status)
app.command("logs", help="Tail logs of the currently-running service.")(
    lifecycle_cmds.logs
)
```

Move the imports up to the existing top-of-file import block if you prefer; keep functional behavior identical.

- [ ] **Step 3: Run all tests**

Run: `pytest tests -q`
Expected: All tests still pass (no regressions).

- [ ] **Step 4: Commit**

```bash
git add src/llm_cli/main.py
git commit -m "refactor(cli): group lifecycle command registrations in main.py"
```

---

### Task 25: Upgrade `stub-runtime` to a working toy TCP server

The current `runtimes/stub-runtime/serve.sh` exits 1, and `healthcheck.sh` always succeeds. Replace them with a real (tiny) loopback TCP server and a port-connect health probe so integration tests can exercise the full lifecycle.

**Files:**
- Create: `runtimes/stub-runtime/stub-server.py`
- Modify: `runtimes/stub-runtime/serve.sh`
- Modify: `runtimes/stub-runtime/healthcheck.sh`

- [ ] **Step 1: Write the failing test (smoke at the runtime level)**

Add to `tests/integration/test_cli_serve.py` (at the very bottom):

```python
import sys


@pytest.fixture
def _real_repo(tmp_path: Path) -> Path:
    """Copy the real stub-runtime + a tiny config into tmp_path/repo."""
    import shutil
    import pytest
    repo = tmp_path / "repo"
    repo.mkdir()
    src_runtime = Path(__file__).resolve().parents[2] / "runtimes" / "stub-runtime"
    if not src_runtime.is_dir():
        pytest.skip("stub-runtime not present in repo layout")
    shutil.copytree(src_runtime, repo / "runtimes" / "stub-runtime")
    md = repo / "models" / "stub-model"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text("id: stub-model\n", encoding="utf-8")
    (md / "pull.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (repo / "configs").mkdir()
    (repo / "configs" / "stub.yaml").write_text(
        "id: stub\nruntime: stub-runtime\nmodel: stub-model\n"
        "serve:\n  host: 127.0.0.1\n  port: 18181\n"
        "readiness:\n  timeout_seconds: 30\n",
        encoding="utf-8",
    )
    return repo


@pytest.mark.skipif(sys.platform == "win32", reason="bash spawn needs POSIX")
def test_stub_runtime_real_background_smoke(tmp_path: Path, _real_repo: Path) -> None:
    _configure(tmp_path, _real_repo)
    try:
        r1 = runner.invoke(app, ["serve", "stub"], catch_exceptions=False)
        assert r1.exit_code == 0, r1.stdout
        rec = read_running(_real_repo)
        assert rec is not None and rec.mode == "background"
        r2 = runner.invoke(app, ["status", "--json"], catch_exceptions=False)
        assert r2.exit_code == 0
        assert '"running": true' in r2.stdout
    finally:
        runner.invoke(app, ["stop"], catch_exceptions=False)
    assert read_running(_real_repo) is None
```

Also add `import pytest` and `from llm_cli.core.lifecycle import read_running` near the top of the same file if not already present.

- [ ] **Step 2: Run smoke (expect failure: serve.sh exits 1)**

Run: `pytest tests/integration/test_cli_serve.py::test_stub_runtime_real_background_smoke -v`
Expected (on POSIX/WSL): FAIL — readiness times out because `serve.sh` exits 1.

- [ ] **Step 3: Write `stub-server.py`**

```python
# runtimes/stub-runtime/stub-server.py
"""Tiny loopback TCP server used by the stub runtime for tests."""
from __future__ import annotations

import os
import signal
import socket
import sys
import threading


def main() -> int:
    host = os.environ.get("LLM_SERVE_HOST", "127.0.0.1")
    port = int(os.environ.get("LLM_SERVE_PORT", "18080"))
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(8)

    stop = threading.Event()

    def _shutdown(*_a) -> None:
        stop.set()
        try:
            sock.close()
        except OSError:
            pass

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    sys.stdout.write(f"stub-server: listening on {host}:{port}\n")
    sys.stdout.flush()

    while not stop.is_set():
        try:
            conn, _ = sock.accept()
        except OSError:
            break
        try:
            conn.sendall(b"stub-runtime: hello\n")
        finally:
            conn.close()
    sys.stdout.write("stub-server: stopped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Rewrite `serve.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$0")/stub-server.py"
```

- [ ] **Step 5: Rewrite `healthcheck.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
HOST="${LLM_SERVE_HOST:-127.0.0.1}"
PORT="${LLM_SERVE_PORT:-18080}"
exec python3 -c "
import socket, sys
s = socket.socket()
s.settimeout(1.0)
try:
    s.connect((sys.argv[1], int(sys.argv[2])))
    sys.exit(0)
except Exception:
    sys.exit(1)
" "$HOST" "$PORT"
```

- [ ] **Step 6: Ensure both scripts are LF-terminated and executable**

From WSL:

```bash
cd /mnt/c/Private/Projects/LocalLLM
dos2unix runtimes/stub-runtime/serve.sh runtimes/stub-runtime/healthcheck.sh 2>/dev/null || \
  python3 -c "import pathlib; [p.write_bytes(p.read_bytes().replace(b'\\r\\n', b'\\n')) for p in pathlib.Path('runtimes/stub-runtime').glob('*.sh')]"
chmod +x runtimes/stub-runtime/serve.sh runtimes/stub-runtime/healthcheck.sh
```

(Windows users without WSL access for this step: rely on `.gitattributes` to enforce LF — the repo already commits these files with LF.)

- [ ] **Step 7: Re-run smoke**

Run (from WSL):
```bash
/home/$USER/llm/.cli-venv/bin/python -m pytest tests/integration/test_cli_serve.py::test_stub_runtime_real_background_smoke -v
```
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add runtimes/stub-runtime/stub-server.py runtimes/stub-runtime/serve.sh runtimes/stub-runtime/healthcheck.sh tests/integration/test_cli_serve.py
git commit -m "feat(stub-runtime): replace no-op scripts with a real toy TCP server"
```

---

### Task 26: `.gitignore` verification

Already correct per inspection — `state/running.json`, `state/history.jsonl`, and `state/logs/` are listed. **No edit needed.** This step is purely a verify-and-skip.

**Files:**
- Verify: `.gitignore`

- [ ] **Step 1: Verify**

Run: `grep -E '^state/' .gitignore`
Expected output:
```
state/running.json
state/history.jsonl
state/logs/
```

If anything is missing, add it; otherwise skip. No commit if no change.

---

## Phase 7 — Documentation

### Task 27: New `docs/lifecycle.md`

**Files:**
- Create: `docs/lifecycle.md`

- [ ] **Step 1: Write the file**

```markdown
# Service lifecycle

`loco` runs **at most one** server at a time. You pick which **config** to serve, and which **mode** to serve it in.

## Modes

| Mode | When to use | Trade-off |
|---|---|---|
| `--foreground` | You want to watch output live and Ctrl-C to stop. | Dies with the terminal. |
| (default — background) | You started a service from a shell and want to keep using that shell. | Survives the shell, but not a logout (no systemd lingering). |
| `--systemd` | You want the service to come back after reboot and survive logout. | Requires `loginctl enable-linger $USER`. |

## Verbs

```bash
loco serve <config>                  # background (default)
loco serve <config> --foreground     # attached
loco serve <config> --systemd        # via ~/.config/systemd/user/loco.service

loco stop                            # stops whatever is running (idempotent)
loco switch <config>                 # stop current, start <config> in the same mode
loco status [--json]                 # what's running, or "not running"
loco logs [-f] [-n N]                # file tail (fg/bg) or journalctl (systemd)
```

## How "what's running" is tracked

- `state/running.json` — single record; gitignored.
- For `--systemd`, `systemctl --user is-active loco.service` is the source of truth; `running.json` is a cache that `loco status` cross-checks.
- A stale PID is auto-reaped on the next `loco status`, `loco stop`, or `loco switch`.

## `loco switch <new>` semantics

- **background**: SIGTERM the current PID, wait ≤10s, escalate to SIGKILL, then start `<new>` in background.
- **systemd**: rewrite `loco.service`, `daemon-reload` if changed, `restart`, wait for readiness.
- **foreground**: refuses with a hint to Ctrl-C the original terminal.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `port <N> is already in use` | Another process bound the port. | `ss -tlnp \| grep <N>` to find owner. |
| `did not become ready in 600s` | `serve.sh` started but `healthcheck.sh` never exited 0 in time. | `loco logs -n 200`; raise `readiness.timeout_seconds` in the config. |
| Systemd service dies after logout | Linger not enabled. | `sudo loginctl enable-linger $USER`. |
| `nothing running` but you think it is | PID was reaped (process died). | `loco status` shows truth; run `loco serve <cfg>` again. |
| `--systemd` says "already serving" | Same config + same unit text already active. | Edit the config or use `loco switch <other>`. |

## Choosing a mode (decision tree)

```
Do you want the service to survive a reboot?
├── yes → --systemd  (and `loginctl enable-linger $USER`)
└── no
    Do you want to watch output live?
    ├── yes → --foreground
    └── no → (default; background)
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/lifecycle.md
git commit -m "docs: add lifecycle.md explaining modes, verbs, and troubleshooting"
```

---

### Task 28: README extension

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Inspect the current CLI table**

Run: `grep -n -A 30 "## CLI" README.md` to locate the table.

- [ ] **Step 2: Add five rows to the CLI table**

In `README.md`, find the table that lists `loco setup`, `loco list`, etc., and add (alphabetical or grouped — match existing order):

```markdown
| `loco serve <cfg> [--foreground\|--systemd]` | Start a config. Background by default. |
| `loco stop` | Stop the currently-running service. |
| `loco switch <cfg>` | Replace the running config with `<cfg>` in the same mode. |
| `loco status [--json]` | Show what's running. Exit 0 either way. |
| `loco logs [-f] [-n N]` | Tail file logs (fg/bg) or journalctl (systemd). |
```

- [ ] **Step 3: Add a one-liner to Getting Started**

After the existing setup steps, add:

```markdown
4. Smoke-test the stub runtime:

   ```bash
   loco serve stub-runtime__stub-model__default
   loco status
   loco stop
   ```
```

Renumber subsequent steps if needed. (If the section already has different content, slot the smoke step in after `loco list`.)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): document lifecycle commands and smoke step"
```

---

### Task 29: `docs/repo-conventions.md` — add `state/` row

**Files:**
- Modify: `docs/repo-conventions.md`

- [ ] **Step 1: Find the "Top-level directories" table**

Run: `grep -n "state" docs/repo-conventions.md` — likely no hit yet.

- [ ] **Step 2: Add a row**

Add to the directory table:

```markdown
| `state/`       | Runtime state (running.json, history.jsonl, logs/). **Gitignored.** Created on first use. Not a configuration source — `loco settings` is. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/repo-conventions.md
git commit -m "docs(conventions): document state/ directory"
```

---

### Task 30: `docs/add-a-runtime.md` — add lifecycle contract section

**Files:**
- Modify: `docs/add-a-runtime.md`

- [ ] **Step 1: Append a new section**

Append to `docs/add-a-runtime.md`:

```markdown
## Lifecycle contract

`loco serve` invokes your scripts via bash inside WSL. Honor these rules:

### `serve.sh`

- Read every input from env vars (no positional args). The CLI passes:
  - `LLM_CONFIG_ID`, `LLM_SERVE_HOST`, `LLM_SERVE_PORT`
  - Every key in `cfg.serve.env` (with `${data_root}` already expanded)
  - The baseline: `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE`
- **End with `exec <server …>`**. This makes the script's PID become the server's PID, so `loco stop` can reach the server with `kill -TERM <pid>` directly.
- Trap nothing in the script itself; let the server handle SIGTERM cleanly (graceful shutdown within ~10s).

### `healthcheck.sh`

- Exit `0` when the service is ready to accept traffic, non-zero otherwise.
- Called repeatedly by `loco serve` until it succeeds or `readiness.timeout_seconds` elapses.
- Receives the same env as `serve.sh`. Don't `curl` external hosts — probe `127.0.0.1:$LLM_SERVE_PORT` (or whatever your runtime exposes).
- Keep it fast (<2s) and side-effect-free.

### State

- Don't write anything to `state/`. That belongs to the CLI.
- Logs go to stdout/stderr; the CLI decides where to redirect (file vs journald).
```

- [ ] **Step 2: Commit**

```bash
git add docs/add-a-runtime.md
git commit -m "docs(add-a-runtime): document serve.sh and healthcheck.sh contracts"
```

---

### Task 31: Spec cross-reference note

**Files:**
- Modify: `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`

- [ ] **Step 1: Add a note near the top**

Find the existing redirection note (added during the settings redesign). Append one bullet:

```markdown
- Lifecycle commands (`serve`, `stop`, `switch`, `status`, `logs`) are designed in [`2026-05-17-lifecycle-and-serve.md`](2026-05-17-lifecycle-and-serve.md). They replace sections 7.2 and 7.3: no `state/active.yaml`, no `loco default`, one managed systemd unit (`loco.service`), and a single in-flight service across all modes.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md
git commit -m "docs(spec): cross-reference lifecycle-and-serve redesign"
```

---

## Phase 8 — `loco doctor` gains a systemd-linger check

### Task 32: `systemd-linger` doctor check

**Files:**
- Modify: `src/llm_cli/core/doctor.py`
- Modify: `tests/unit/test_doctor_check.py`

- [ ] **Step 1: Read the existing check structure**

Run: `cat src/llm_cli/core/doctor.py | head -60`
Identify how an existing requirement (e.g. CUDA driver) is implemented — there's a registry, a detect function, and a comparison against `requirements.yaml`. Linger is **not** a versioned requirement; it's a binary check. Implement it as a new optional check that always runs (regardless of `requirements.yaml`), with an `id` of `systemd-linger`.

- [ ] **Step 2: Write the failing test**

Append to `tests/unit/test_doctor_check.py`:

```python
from unittest.mock import patch

from llm_cli.core.doctor import detect_systemd_linger


def test_detect_systemd_linger_true():
    fake = type("R", (), {"returncode": 0, "stdout": "Linger=yes\n"})()
    with patch("llm_cli.core.doctor.subprocess.run", return_value=fake):
        assert detect_systemd_linger() == "yes"


def test_detect_systemd_linger_false():
    fake = type("R", (), {"returncode": 0, "stdout": "Linger=no\n"})()
    with patch("llm_cli.core.doctor.subprocess.run", return_value=fake):
        assert detect_systemd_linger() == "no"


def test_detect_systemd_linger_missing_tool():
    with patch("llm_cli.core.doctor.subprocess.run", side_effect=FileNotFoundError):
        assert detect_systemd_linger() is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_doctor_check.py -k linger -v`
Expected: ImportError on `detect_systemd_linger`.

- [ ] **Step 4: Write minimal implementation**

In `src/llm_cli/core/doctor.py`, add (above the `check_all` function):

```python
import subprocess as _subprocess


def detect_systemd_linger() -> str | None:
    """Return 'yes' / 'no' / None (when loginctl missing)."""
    try:
        r = _subprocess.run(
            ["loginctl", "show-user", "--property=Linger", os.environ.get("USER", "")],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for line in (r.stdout or "").splitlines():
        if line.startswith("Linger="):
            return line.split("=", 1)[1].strip().lower()
    return None
```

Add `import os` at the top of the file if missing.

Then in the `check_all` function (or wherever results are assembled), append a synthesized result so the existing `loco doctor` table picks it up. Match the existing `CheckResult` shape — likely:

```python
from llm_cli.core.doctor import CheckResult, CheckStatus  # already exported
# Inside check_all, after the loop over requirements:
linger = detect_systemd_linger()
if linger is None:
    status, hint = CheckStatus.UNKNOWN, "loginctl not found; install systemd-services if you want --systemd."
elif linger == "yes":
    status, hint = CheckStatus.OK, ""
else:
    status, hint = CheckStatus.OUTDATED, "sudo loginctl enable-linger $USER (so --systemd survives logout)"
results.append(
    CheckResult(
        requirement=Requirement(
            id="systemd-linger",
            name="systemd user lingering",
            min_version=None,
            install_hint=hint,
        ),
        status=status,
        detected_version=linger or "-",
    )
)
```

(If the existing module's `Requirement` / `CheckResult` field names differ, mirror the local shape — the test in Step 2 only depends on the standalone `detect_systemd_linger()` function.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_doctor_check.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/core/doctor.py tests/unit/test_doctor_check.py
git commit -m "feat(doctor): add systemd-linger check with sudo enable hint"
```

---

## Phase 9 — End-to-end smoke

### Task 33: WSL smoke run

This is a manual / scripted verification, not a TDD task.

**Files:**
- None (script-only).

- [ ] **Step 1: Run full test suite from WSL**

```bash
cd /mnt/c/Private/Projects/LocalLLM
/home/$USER/llm/.cli-venv/bin/python -m pytest tests -q
```

Expected: all tests pass. Systemd integration test is skipped unless `systemctl --user` works.

- [ ] **Step 2: End-to-end background smoke**

```bash
loco serve stub-runtime__stub-model__default
loco status
# Verify "running" with port 18080.
curl -s 127.0.0.1:18080 || true   # may print "stub-runtime: hello" then EOF
loco logs -n 5
loco stop
loco status   # should print "not running"
```

- [ ] **Step 3: End-to-end switch smoke**

Create a second stub config with a different port (e.g. copy `configs/stub-runtime__stub-model__default.yaml` → `stub-runtime__stub-model__alt.yaml`, change `id:` and `port:` to 18081).

```bash
loco serve stub-runtime__stub-model__default
loco switch stub-runtime__stub-model__alt
loco status   # config should be the alt
loco stop
```

- [ ] **Step 4: (Optional, if systemctl --user works) systemd smoke**

```bash
loco serve stub-runtime__stub-model__default --systemd
loco status
systemctl --user is-active loco.service   # active
loco switch stub-runtime__stub-model__alt
systemctl --user status loco.service --no-pager  # should reference alt config in Description
loco stop
```

- [ ] **Step 5: Commit (no-op if everything passes)**

Nothing to commit unless smoke surfaced fixes. If it did, commit those individually with `fix(...)`/`docs(...)` prefixes.

---

## Self-review checklist (run after writing — not for the executor)

1. **Spec coverage** — every section of `2026-05-17-lifecycle-and-serve.md` has at least one task:
   - §5.1 surface → Tasks 15, 16, 17, 19, 21, 22, 23
   - §5.2 state files → Tasks 1, 2, 3, 26
   - §5.3 truth model → Task 5 (reconcile)
   - §5.4 per-mode mechanics → Tasks 15, 16, 17, 21, 23
   - §5.5 systemd unit body → Tasks 11, 13, 17
   - §5.6 readiness → Tasks 8, 15, 17
   - §5.7 port-in-use → Tasks 6, 15
   - §5.8 status text/JSON → Task 22
   - §5.9 edge cases → Tasks 15, 19, 20, 21, 23
   - §6 module layout → Phases 1–5
   - §7 testing → Tasks 1–10, 15–23
   - §8 docs → Tasks 27–31
   - §9 open/deferred → not implemented (correct: they're deferred)
   - linger doctor → Task 32
2. **Placeholder scan** — no "TBD", no "fill in details". Where the existing codebase shape needs to be matched (Task 32's `CheckResult`/`Requirement` fields), the task says explicitly "mirror the local shape" with the test pinning down the contract.
3. **Type consistency** — `LifecycleRecord` field names (`mode`, `config_id`, `port`, `started_at`, `pid`, `log_path`, `unit`) are used identically in lifecycle.py, serve.py, lifecycle_cmds.py, and tests. The systemd unit name is `loco.service` everywhere.
