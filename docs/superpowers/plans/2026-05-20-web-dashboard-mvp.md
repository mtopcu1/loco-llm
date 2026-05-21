# Web Dashboard MVP (Plan 1/5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working `loco dashboard install` + `loco dashboard serve` that opens a browser to a usable read-only monitoring dashboard covering all v1 pages (Overview, Runtimes, Models, Configs, Instance, Doctor, Disk, History, Settings). No mutations, no jobs, no metrics scrape, no `--insecure` UX. Baseline security (Host header / CORS / CSP / Request-ID) is in place from day one.

**Architecture:** New `webapi` Python package containing a FastAPI factory that mounts read-only routes under `/api/*` and serves the built React SPA from `dashboard/dist/` at `/`. Routes call into `llm_cli.core.*` for data (never raw file writes — that's a Plan 2 concern but the contract is enforced now). Real-time read-only streams (instance state, instance logs, history appends) use SSE via `sse-starlette`. React SPA built with Vite, React 19, TypeScript, Tailwind v4, shadcn/ui, TanStack Router, TanStack Query, Zustand, sonner. Backend launched as a detached uvicorn process by `loco dashboard serve` (background by default, `--foreground` available).

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, sse-starlette, httpx, Typer, pytest. React 19, TypeScript, Vite, Tailwind v4, shadcn/ui, TanStack Router, TanStack Query, Zustand, sonner, Vitest + Testing Library + msw. CI on GitHub Actions.

**Related spec:** `docs/superpowers/specs/2026-05-20-web-dashboard-design.md`

**This is Plan 1 of 5.** Subsequent plans (written after this one merges):

- Plan 2 — Mutations & jobs system (POST/PUT/DELETE routes, `core/jobs.py`, jobs tray UI)
- Plan 3 — Param grid + new-config wizard
- Plan 4 — Live metrics pipeline (manifest extension, scrape task, aggregation)
- Plan 5 — Security hardening (`--insecure` + `--i-understand` + banner + `DASHBOARD-SECURITY.md`), update notifier, performance budgets, full CI polish

**Implementation branch:** create `feat/web-dashboard-mvp` from `main` before Task 1 (project convention — never commit on `main`).

---

## Background — what exists today

- **CLI structure:** Typer app in `src/llm_cli/main.py`. Subcommands live in `src/llm_cli/commands/` and call into `src/llm_cli/core/`. Pattern is well-established (see `runtime_cmd.py`, `model_cmd.py`, `lifecycle_cmds.py`).
- **Registry / core data access:** `core/registry.py` lists runtimes and configs from disk. `core/model_registry.py` reads `$LLM_MODELS/registry.json`. `core/install_record.py` manages `runtimes/<id>/.installed`. `core/lifecycle_status.py` reads `state/running.json`. `core/lifecycle.py` reads/writes `state/history.jsonl`. All are pure-Python and already used by both interactive CLI flows and tests.
- **Settings:** `core/settings.py` with `KEY_REGISTRY` driving setting types (`kind: path` etc). `load_settings()` / `resolve_settings()` already separate stored vs effective.
- **Doctor:** `core/doctor.py` runs scoped checks from `requirements.yaml`. Adding a new `dashboard` scope is a known pattern (see existing `default` / `runtime` scopes).
- **Setup chain:** `commands/setup.py` runs a y/n chain of optional steps. Adding one more step is pure addition.
- **Update:** `commands/update_cmd.py` handles git-tag-based self-updates. Adding a post-update hook is pure addition.
- **Tests:** `tests/` uses `pytest`, `pytest-mock`, `pexpect` for PTY-driven TUI tests. Existing fixtures isolate `LLM_DATA_ROOT` to `tmp_path`. `pyproject.toml` defines a `tui` pytest marker; we'll add `webapi`.
- **CI:** Single `tests` GH Actions job, PR-only, uses `uv`. We'll add two new jobs: `dashboard-tests` and `api-contract-check`.

---

## File map

**Create (Python source):**
- `src/llm_cli/commands/dashboard_cmd.py` — Typer subcommand group
- `src/llm_cli/core/dashboard.py` — install lifecycle, `.installed` marker, `dist_hash`, server-PID helpers
- `src/llm_cli/core/disk.py` — `du` wrappers for the Disk page
- `src/llm_cli/webapi/__init__.py`
- `src/llm_cli/webapi/app.py` — `create_app()` factory
- `src/llm_cli/webapi/deps.py` — FastAPI dependency injectables
- `src/llm_cli/webapi/errors.py` — `ErrorCode` enum + exception handlers
- `src/llm_cli/webapi/middleware.py` — `HostHeaderMiddleware`, `SecurityHeadersMiddleware`, `RequestIDMiddleware`
- `src/llm_cli/webapi/streams.py` — `EventHub` + SSE helpers
- `src/llm_cli/webapi/static.py` — SPA serving with fallback
- `src/llm_cli/webapi/export_openapi.py` — `python -m llm_cli.webapi.export_openapi`
- `src/llm_cli/webapi/routes/__init__.py`
- `src/llm_cli/webapi/routes/health.py`
- `src/llm_cli/webapi/routes/version.py`
- `src/llm_cli/webapi/routes/overview.py`
- `src/llm_cli/webapi/routes/runtimes.py`
- `src/llm_cli/webapi/routes/models.py`
- `src/llm_cli/webapi/routes/configs.py`
- `src/llm_cli/webapi/routes/instance.py`
- `src/llm_cli/webapi/routes/doctor.py`
- `src/llm_cli/webapi/routes/settings.py`
- `src/llm_cli/webapi/routes/disk.py`
- `src/llm_cli/webapi/routes/history.py`

**Create (React source):**
- `dashboard/package.json`
- `dashboard/package-lock.json` (generated)
- `dashboard/vite.config.ts`
- `dashboard/tailwind.config.ts`
- `dashboard/postcss.config.js`
- `dashboard/tsconfig.json`
- `dashboard/tsconfig.node.json`
- `dashboard/index.html`
- `dashboard/README.md`
- `dashboard/components.json` (shadcn init)
- `dashboard/src/main.tsx`
- `dashboard/src/App.tsx`
- `dashboard/src/router.tsx` — TanStack Router route tree
- `dashboard/src/queryClient.ts` — TanStack Query setup
- `dashboard/src/store.ts` — Zustand cross-page state
- `dashboard/src/styles/globals.css`
- `dashboard/src/api/generated.ts` — codegen output (committed)
- `dashboard/src/api/client.ts` — thin wrapper over generated client
- `dashboard/src/components/Layout.tsx`
- `dashboard/src/components/Header.tsx`
- `dashboard/src/components/Sidebar.tsx`
- `dashboard/src/components/SecurityBanner.tsx` — placeholder, always hidden in Plan 1
- `dashboard/src/components/ErrorCard.tsx`
- `dashboard/src/components/StatusPill.tsx`
- `dashboard/src/components/ui/*` — shadcn-generated primitives (button, card, table, tabs, badge, input, sonner, etc.)
- `dashboard/src/hooks/useSSE.ts`
- `dashboard/src/features/overview/OverviewPage.tsx`
- `dashboard/src/features/runtimes/RuntimesPage.tsx`
- `dashboard/src/features/runtimes/RuntimeDetailPage.tsx`
- `dashboard/src/features/models/ModelsPage.tsx`
- `dashboard/src/features/models/ModelDetailPage.tsx`
- `dashboard/src/features/configs/ConfigsPage.tsx`
- `dashboard/src/features/configs/ConfigDetailPage.tsx`
- `dashboard/src/features/instance/InstancePage.tsx`
- `dashboard/src/features/instance/LogsView.tsx`
- `dashboard/src/features/doctor/DoctorPage.tsx`
- `dashboard/src/features/disk/DiskPage.tsx`
- `dashboard/src/features/history/HistoryPage.tsx`
- `dashboard/src/features/settings/SettingsPage.tsx`
- `dashboard/src/lib/format.ts`

**Create (scripts/docs/tests):**
- `scripts/regen-api-client.sh`
- `docs/DASHBOARD.md` — user-facing install/serve/uninstall guide
- `tests/webapi/__init__.py`
- `tests/webapi/conftest.py`
- `tests/webapi/test_middleware.py`
- `tests/webapi/test_routes_health_version.py`
- `tests/webapi/test_routes_runtimes.py`
- `tests/webapi/test_routes_models.py`
- `tests/webapi/test_routes_configs.py`
- `tests/webapi/test_routes_instance.py`
- `tests/webapi/test_routes_doctor.py`
- `tests/webapi/test_routes_settings.py`
- `tests/webapi/test_routes_disk.py`
- `tests/webapi/test_routes_history.py`
- `tests/webapi/test_routes_overview.py`
- `tests/webapi/test_streams.py`
- `tests/unit/test_core_dashboard.py`
- `tests/unit/test_core_disk.py`
- `tests/unit/test_cli_dashboard.py`
- `dashboard/src/**/__tests__/*.test.tsx` — per-page Vitest tests
- `dashboard/vitest.config.ts`
- `dashboard/src/test/setup.ts` — msw setup
- `dashboard/src/test/handlers.ts` — msw request handlers
- `.github/workflows/dashboard-tests.yml`
- `.github/workflows/api-contract-check.yml`

**Modify:**
- `pyproject.toml` — add `[project.optional-dependencies] dashboard = [...]`, add `webapi` pytest marker
- `requirements.yaml` — add `scope: dashboard` entries for `node` and `npm`
- `requirements.md` — regenerated from `requirements.yaml`
- `src/llm_cli/main.py` — wire `dashboard_cmd.app` as a Typer subcommand
- `src/llm_cli/commands/setup.py` — add opt-in dashboard step at end of chain
- `src/llm_cli/commands/update_cmd.py` — auto-rebuild dashboard if `.installed` exists and CLI version changed
- `src/llm_cli/commands/doctor.py` — add `dashboard` scope dispatcher
- `src/llm_cli/core/doctor.py` — add `_dashboard_scope_checks()` function
- `.gitignore` — add `dashboard/node_modules/`, `dashboard/dist/`, `dashboard/.installed`, `state/jobs/`, `state/metrics/`, `state/dashboard/`
- `.gitattributes` — add `*.tsx text eol=lf`, `*.ts text eol=lf`, `dashboard/package-lock.json binary`
- `docs/README.md` — add link to `docs/DASHBOARD.md`

**Untouched in Plan 1 (later plans):**
- `core/jobs.py` (Plan 2)
- `core/metrics.py` (Plan 4)
- Existing runtime manifests (Plan 4 adds `metrics:` block)
- `core/param_grid_models.py` etc. (Plan 3 surfaces the param grid in React)

---

## Conventions used throughout this plan

- **TDD discipline:** every code change has a failing test first. Steps are: write the failing test → run it to verify FAIL → implement → run to verify PASS → commit.
- **Commit cadence:** one commit per task (not per step). Commit messages use [conventional commits](https://www.conventionalcommits.org/) — see `.cursor/rules/conventional-commits.mdc`.
- **Test isolation:** Python tests use `tmp_path` + monkeypatched `LLM_DATA_ROOT`. Frontend tests use msw to intercept `/api/*`.
- **No raw file writes from `webapi/routes/`** — every route handler delegates to `llm_cli.core.*`. If a route needs functionality not yet in `core/*`, extract it from a `commands/*` module into `core/*` as a sub-step.
- **Shell commands assume bash** (project is WSL2-only at runtime). Windows-host commands shown only when necessary.

---

## Phase A — Python foundation

### Task 1: Add dashboard Python deps + pytest marker

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the optional-deps group**

In `pyproject.toml`, add after the existing `[project.optional-dependencies] dev = [...]` block:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pexpect>=4.9; sys_platform != 'win32'",
    "build>=1.0",
]
dashboard = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.30,<1.0",
    "sse-starlette>=2.1,<3.0",
]
```

(`httpx>=0.27` is already in `dependencies`, so dashboard reuses it.)

- [ ] **Step 2: Add the pytest marker**

In `[tool.pytest.ini_options]`, extend `markers`:

```toml
markers = [
    "tui: PTY-driven TUI integration tests (Unix only)",
    "webapi: FastAPI dashboard backend tests",
]
```

- [ ] **Step 3: Sync the venv**

```bash
uv pip install -e ".[dev,dashboard]"
```

Expected: installs fastapi, uvicorn, sse-starlette without error.

- [ ] **Step 4: Verify imports**

```bash
python -c "import fastapi, uvicorn, sse_starlette; print(fastapi.__version__, uvicorn.__version__, sse_starlette.__version__)"
```

Expected: three version strings printed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): add dashboard optional-deps group and webapi pytest marker"
```

---

### Task 2: Add Node + npm to requirements + regenerate requirements.md

**Files:**
- Modify: `requirements.yaml`
- Modify: `requirements.md` (regenerated)

- [ ] **Step 1: Inspect current requirements.yaml structure**

```bash
head -n 80 requirements.yaml
```

Find the scope/section pattern used (e.g., `default`, `runtime`).

- [ ] **Step 2: Add the dashboard scope**

Append to `requirements.yaml`:

```yaml
- name: Node.js
  scope: dashboard
  check: node --version
  min_version: "20.0.0"
  install_hint: |
    Install Node.js 20+:
      WSL/Linux: `curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && nvm install --lts`
      macOS:     `brew install node`
  required_for: "loco dashboard install / serve"

- name: npm
  scope: dashboard
  check: npm --version
  min_version: "10.0.0"
  install_hint: "Bundled with Node.js (see Node.js install hint)."
  required_for: "loco dashboard install / serve"
```

(Adjust schema to match exactly what `requirements.yaml` already uses — read the file first.)

- [ ] **Step 3: Regenerate requirements.md**

```bash
loco doctor render-requirements
```

- [ ] **Step 4: Verify by viewing the diff**

```bash
git diff requirements.md
```

Expected: the dashboard scope appears in the rendered output.

- [ ] **Step 5: Commit**

```bash
git add requirements.yaml requirements.md
git commit -m "chore(doctor): add dashboard scope (node, npm) to requirements"
```

---

### Task 3: Update .gitignore + .gitattributes

**Files:**
- Modify: `.gitignore`
- Modify: `.gitattributes`

- [ ] **Step 1: Append to .gitignore**

```
# Dashboard
dashboard/node_modules/
dashboard/dist/
dashboard/.installed

# Dashboard server / job / metrics state
state/dashboard/
state/jobs/
state/metrics/
```

- [ ] **Step 2: Append to .gitattributes**

```
# Dashboard frontend
*.ts        text eol=lf
*.tsx       text eol=lf
*.mjs       text eol=lf
dashboard/package-lock.json text eol=lf
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore .gitattributes
git commit -m "chore(repo): ignore dashboard build artifacts, server state, metrics; normalize TS line endings"
```

---

### Task 4: `core/dashboard.py` — install lifecycle helpers

**Files:**
- Create: `src/llm_cli/core/dashboard.py`
- Create: `tests/unit/test_core_dashboard.py`

This module owns:
- `dashboard_root()` — returns `Path(repo_root) / "dashboard"`
- `dist_dir()` — returns `dashboard/dist`
- `installed_marker_path()` — returns `dashboard/.installed`
- `compute_dist_hash(dist_dir: Path) -> str` — sha256 over sorted `(relative_path, content_bytes)` of every file under `dist/`
- `load_installed_record() -> InstalledRecord | None`
- `write_installed_record(record: InstalledRecord) -> None`
- `verify_installed(cli_version: str) -> InstallVerdict` — returns one of `("ok", "")`, `("missing", reason)`, `("version_mismatch", reason)`, `("hash_mismatch", reason)`, `("dist_missing", reason)`
- `InstalledRecord` dataclass: `installed_at: str`, `cli_version: str`, `node_version: str`, `npm_version: str`, `dist_hash: str`
- `InstallVerdict` — `tuple[Literal["ok","missing","version_mismatch","hash_mismatch","dist_missing"], str]`

Server-PID helpers:
- `server_pid_path()` — `state/dashboard/server.pid`
- `server_log_path()` — `state/dashboard/server.log`
- `read_server_pid() -> int | None`
- `is_server_alive(pid: int) -> bool` — `kill -0` style check (use `os.kill(pid, 0)` with `OSError` handling)

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_core_dashboard.py`:

```python
import json
import os
import time
from pathlib import Path

import pytest

from llm_cli.core import dashboard as dash


def _write_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "main.css").write_text("body{}", encoding="utf-8")
    (assets / "main.js").write_text("console.log(0)", encoding="utf-8")
    return dist


def test_compute_dist_hash_stable(tmp_path):
    d = _write_dist(tmp_path)
    h1 = dash.compute_dist_hash(d)
    h2 = dash.compute_dist_hash(d)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_compute_dist_hash_changes_on_edit(tmp_path):
    d = _write_dist(tmp_path)
    h1 = dash.compute_dist_hash(d)
    (d / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    h2 = dash.compute_dist_hash(d)
    assert h1 != h2


def test_installed_record_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.1.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash="sha256:abc",
    )
    dash.write_installed_record(rec)
    loaded = dash.load_installed_record()
    assert loaded == rec


def test_verify_installed_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    verdict, reason = dash.verify_installed("1.1.0")
    assert verdict == "missing"


def test_verify_installed_version_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    d = _write_dist(tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.0.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash=dash.compute_dist_hash(d),
    )
    dash.write_installed_record(rec)
    verdict, _ = dash.verify_installed("1.1.0")
    assert verdict == "version_mismatch"


def test_verify_installed_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    d = _write_dist(tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.1.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash="sha256:WRONG",
    )
    dash.write_installed_record(rec)
    verdict, _ = dash.verify_installed("1.1.0")
    assert verdict == "hash_mismatch"


def test_verify_installed_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    d = _write_dist(tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.1.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash=dash.compute_dist_hash(d),
    )
    dash.write_installed_record(rec)
    verdict, _ = dash.verify_installed("1.1.0")
    assert verdict == "ok"


def test_is_server_alive_self_pid():
    assert dash.is_server_alive(os.getpid()) is True


def test_is_server_alive_nonexistent():
    assert dash.is_server_alive(999999) is False
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/unit/test_core_dashboard.py -v
```

Expected: `ImportError` or all tests fail (module not yet implemented).

- [ ] **Step 3: Implement `core/dashboard.py`**

```python
"""Dashboard install lifecycle helpers."""
from __future__ import annotations

import hashlib
import os
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
            "repo_root not configured. Run `loco setup` or set repo_root via "
            "`loco settings edit repo_root`."
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


# --- server PID helpers ----------------------------------------------------

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
    except (OSError, PermissionError):
        return pid > 0 and _err_was_perm()
    except ProcessLookupError:
        return False


def _err_was_perm() -> bool:
    # On Linux, sending signal 0 to a process you don't own raises PermissionError,
    # which is still proof the process exists. Distinguish here.
    import errno
    return getattr(os, "errno", None) == errno.EPERM
```

(If the `_err_was_perm` heuristic feels unreliable, simplify to `try: os.kill(pid, 0); return True; except: return False` — accepted trade-off for v1.)

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/unit/test_core_dashboard.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/dashboard.py tests/unit/test_core_dashboard.py
git commit -m "feat(dashboard): core install lifecycle helpers (dist_hash, .installed, server-pid)"
```

---

### Task 5: `core/disk.py` — du wrappers

**Files:**
- Create: `src/llm_cli/core/disk.py`
- Create: `tests/unit/test_core_disk.py`

Scope: a single `scan() -> DiskReport` function returning total/free of data_root, list of model entries with bytes-on-disk, cache size. Uses `shutil.disk_usage()` + per-path recursive size (no shell `du` — Python `Path.rglob` is fine for v1).

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

import pytest

from llm_cli.core import disk


def _seed_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data_root"
    (root / "models" / "m1").mkdir(parents=True)
    (root / "models" / "m1" / "weights.bin").write_bytes(b"x" * 1000)
    (root / "models" / "m2").mkdir(parents=True)
    (root / "models" / "m2" / "weights.bin").write_bytes(b"y" * 500)
    (root / "cache" / "hf").mkdir(parents=True)
    (root / "cache" / "hf" / "blob").write_bytes(b"z" * 250)
    return root


def test_scan_reports_models(tmp_path, monkeypatch):
    root = _seed_data_root(tmp_path)
    monkeypatch.setattr(disk, "_models_dir", lambda: root / "models")
    monkeypatch.setattr(disk, "_cache_dir", lambda: root / "cache")
    monkeypatch.setattr(disk, "_data_root", lambda: root)
    report = disk.scan()
    by_id = {m.id: m for m in report.models}
    assert by_id["m1"].bytes == 1000
    assert by_id["m2"].bytes == 500
    assert report.cache_bytes == 250
    assert report.data_root_bytes_used >= 1750


def test_scan_handles_empty_models(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    (root / "models").mkdir(parents=True)
    (root / "cache").mkdir(parents=True)
    monkeypatch.setattr(disk, "_models_dir", lambda: root / "models")
    monkeypatch.setattr(disk, "_cache_dir", lambda: root / "cache")
    monkeypatch.setattr(disk, "_data_root", lambda: root)
    report = disk.scan()
    assert report.models == []
    assert report.cache_bytes == 0
```

- [ ] **Step 2: Run — FAIL**

```bash
pytest tests/unit/test_core_disk.py -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run — PASS**

```bash
pytest tests/unit/test_core_disk.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/disk.py tests/unit/test_core_disk.py
git commit -m "feat(disk): per-model disk usage and data-root capacity scan"
```

---

### Task 6: `commands/dashboard_cmd.py` — Typer subcommand skeleton + main wiring

**Files:**
- Create: `src/llm_cli/commands/dashboard_cmd.py`
- Modify: `src/llm_cli/main.py`
- Create: `tests/unit/test_cli_dashboard.py`

This task lands the CLI surface as stubs. Each subcommand prints "not yet implemented in plan 1, task NN" except `status` and `uninstall` which are simple enough to ship now.

- [ ] **Step 1: Write failing tests**

```python
import pytest
from typer.testing import CliRunner

from llm_cli.main import app


runner = CliRunner()


def test_llm_dashboard_help_lists_subcommands():
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    for sub in ("install", "serve", "status", "stop", "uninstall"):
        assert sub in out


def test_llm_dashboard_status_when_not_installed(tmp_path, monkeypatch):
    # repo_root unset → status should say "not installed" gracefully
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["dashboard", "status"])
    # Either exit 0 with "not installed" or exit 1 with friendly error — both OK.
    assert "dashboard" in result.stdout.lower() or "dashboard" in (result.stderr or "").lower()
```

- [ ] **Step 2: Run — FAIL**

```bash
pytest tests/unit/test_cli_dashboard.py -v
```

- [ ] **Step 3: Implement `commands/dashboard_cmd.py`**

```python
"""`loco dashboard ...` command group."""
from __future__ import annotations

from typing import Annotated

import typer

from llm_cli.core import dashboard as dash

app = typer.Typer(help="Manage the LocalLLM web dashboard.")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Bare `loco dashboard` → alias for `loco dashboard serve`."""
    if ctx.invoked_subcommand is None:
        serve()


@app.command()
def install(
    reset: Annotated[bool, typer.Option("--reset", help="Wipe node_modules first.")] = False,
    skip_frontend: Annotated[bool, typer.Option("--skip-frontend")] = False,
    skip_python: Annotated[bool, typer.Option("--skip-python")] = False,
) -> None:
    """Install Python deps + Node deps + build the frontend."""
    typer.secho("`loco dashboard install` not yet implemented (Plan 1, Task 13).", fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port")] = 7878,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    foreground: Annotated[bool, typer.Option("--foreground")] = False,
    no_open: Annotated[bool, typer.Option("--no-open")] = False,
) -> None:
    """Start the dashboard server."""
    typer.secho("`loco dashboard serve` not yet implemented (Plan 1, Task 14).", fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@app.command()
def status() -> None:
    """Print dashboard install + server status."""
    record = dash.load_installed_record()
    if record is None:
        typer.echo("Dashboard not installed. Run `loco dashboard install`.")
        raise typer.Exit(code=0)
    typer.echo(f"Installed for CLI {record.cli_version} at {record.installed_at}")
    pid = dash.read_server_pid()
    if pid is None:
        typer.echo("Server: not running")
        return
    alive = dash.is_server_alive(pid)
    typer.echo(f"Server: {'running' if alive else 'stale pid file'} (pid={pid})")


@app.command()
def stop() -> None:
    """Stop the dashboard server."""
    typer.secho("`loco dashboard stop` not yet implemented (Plan 1, Task 15).", fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@app.command()
def uninstall(
    purge: Annotated[bool, typer.Option("--purge", help="Delete dashboard/dist and dashboard/node_modules.")] = False,
) -> None:
    """Remove the .installed marker (and optionally build artifacts)."""
    typer.secho("`loco dashboard uninstall` not yet implemented (Plan 1, Task 15).", fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)
```

- [ ] **Step 4: Wire into `main.py`**

In `src/llm_cli/main.py`, after the other `app.add_typer(...)` lines, add:

```python
from llm_cli.commands.dashboard_cmd import app as dashboard_app

app.add_typer(dashboard_app, name="dashboard")
```

- [ ] **Step 5: Run — PASS**

```bash
pytest tests/unit/test_cli_dashboard.py -v
loco dashboard --help
```

Expected: help output lists install / serve / status / stop / uninstall.

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/commands/dashboard_cmd.py src/llm_cli/main.py tests/unit/test_cli_dashboard.py
git commit -m "feat(dashboard): wire `loco dashboard` subcommand group with status stub"
```

---

## Phase B — FastAPI shell

### Task 7: `webapi/errors.py` — uniform error shape

**Files:**
- Create: `src/llm_cli/webapi/__init__.py` (empty)
- Create: `src/llm_cli/webapi/errors.py`
- Create: `tests/webapi/__init__.py` (empty)
- Create: `tests/webapi/conftest.py`
- Create: `tests/webapi/test_errors.py`

- [ ] **Step 1: Write failing tests**

`tests/webapi/conftest.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_cli.webapi.errors import ApiError, ErrorCode, install_exception_handlers


@pytest.fixture
def error_app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/raise/{code_name}")
    def _raise(code_name: str):
        raise ApiError(
            code=ErrorCode[code_name],
            message=f"raised {code_name}",
            details={"code_name": code_name},
            status_code=400,
        )

    @app.get("/boom")
    def _boom():
        raise RuntimeError("synthetic")

    return app


@pytest.fixture
def client(error_app) -> TestClient:
    return TestClient(error_app, raise_server_exceptions=False)
```

`tests/webapi/test_errors.py`:

```python
import pytest


@pytest.mark.webapi
def test_api_error_response_shape(client):
    r = client.get("/raise/RUNTIME_NOT_INSTALLED")
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "RUNTIME_NOT_INSTALLED"
    assert body["error"]["message"] == "raised RUNTIME_NOT_INSTALLED"
    assert body["error"]["details"] == {"code_name": "RUNTIME_NOT_INSTALLED"}
    assert "request_id" in body


@pytest.mark.webapi
def test_unhandled_exception_returns_500_without_stack(client):
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "synthetic" not in body["error"]["message"]
    assert "request_id" in body
```

- [ ] **Step 2: Run — FAIL** (`pytest tests/webapi/ -v`)

- [ ] **Step 3: Implement `webapi/errors.py`**

```python
"""Uniform error response shape for the webapi."""
from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("llm_cli.webapi.errors")


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"

    DASHBOARD_NOT_INSTALLED = "DASHBOARD_NOT_INSTALLED"
    DASHBOARD_VERSION_MISMATCH = "DASHBOARD_VERSION_MISMATCH"

    RUNTIME_NOT_FOUND = "RUNTIME_NOT_FOUND"
    RUNTIME_NOT_INSTALLED = "RUNTIME_NOT_INSTALLED"
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"

    INSTANCE_NOT_RUNNING = "INSTANCE_NOT_RUNNING"
    INSTANCE_ALREADY_RUNNING = "INSTANCE_ALREADY_RUNNING"

    SETTINGS_UNKNOWN_KEY = "SETTINGS_UNKNOWN_KEY"


class ApiError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        fix_hint: str | None = None,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.fix_hint = fix_hint
        self.status_code = status_code
        super().__init__(message)


def _error_body(
    code: str, message: str, details: dict[str, Any], fix_hint: str | None, request: Request
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "fix_hint": fix_hint,
        },
        "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
    }


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code.value, exc.message, exc.details, exc.fix_hint, request),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception", extra={"request_id": getattr(request.state, "request_id", "?")})
        return JSONResponse(
            status_code=500,
            content=_error_body(
                ErrorCode.INTERNAL_ERROR.value,
                "An unexpected error occurred. Check server logs for details.",
                {},
                None,
                request,
            ),
        )
```

- [ ] **Step 4: Run — PASS**

```bash
pytest tests/webapi/test_errors.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/webapi/__init__.py src/llm_cli/webapi/errors.py tests/webapi/
git commit -m "feat(webapi): uniform ApiError response shape with ErrorCode enum"
```

---

### Task 8: `webapi/middleware.py` — Host header + security headers + request-id

**Files:**
- Create: `src/llm_cli/webapi/middleware.py`
- Create: `tests/webapi/test_middleware.py`

- [ ] **Step 1: Write failing tests**

`tests/webapi/test_middleware.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_cli.webapi.middleware import (
    HostHeaderMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.add_middleware(SecurityHeadersMiddleware)
    a.add_middleware(HostHeaderMiddleware, allowed_hosts={"127.0.0.1:7878", "localhost:7878"})
    a.add_middleware(RequestIDMiddleware)

    @a.get("/")
    def _root():
        return {"ok": True}

    return a


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.mark.webapi
def test_request_id_header_present(client):
    r = client.get("/", headers={"Host": "127.0.0.1:7878"})
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
    assert len(r.headers["X-Request-ID"]) >= 16


@pytest.mark.webapi
def test_host_header_allowed(client):
    r = client.get("/", headers={"Host": "127.0.0.1:7878"})
    assert r.status_code == 200


@pytest.mark.webapi
def test_host_header_rejected_returns_421(client):
    r = client.get("/", headers={"Host": "evil.example.com"})
    assert r.status_code == 421


@pytest.mark.webapi
def test_security_headers_present(client):
    r = client.get("/", headers={"Host": "127.0.0.1:7878"})
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
"""Webapi middleware: Host header allow-list, security headers, request-id."""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'"
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class HostHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_hosts: set[str]) -> None:
        super().__init__(app)
        self.allowed_hosts = {h.lower() for h in allowed_hosts}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = (request.headers.get("host") or "").lower()
        if host not in self.allowed_hosts:
            return JSONResponse(
                status_code=421,
                content={
                    "error": {
                        "code": "BAD_HOST_HEADER",
                        "message": f"Host header '{host}' is not allowed.",
                        "details": {"allowed": sorted(self.allowed_hosts)},
                        "fix_hint": None,
                    },
                    "request_id": getattr(request.state, "request_id", uuid.uuid4().hex),
                },
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "()"
        response.headers["Content-Security-Policy"] = CSP
        return response
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/webapi/middleware.py tests/webapi/test_middleware.py
git commit -m "feat(webapi): host-header allow-list, security headers, request-id middleware"
```

---

### Task 9: `webapi/streams.py` — EventHub + SSE helpers

**Files:**
- Create: `src/llm_cli/webapi/streams.py`
- Create: `tests/webapi/test_streams.py`

- [ ] **Step 1: Write failing tests**

```python
import asyncio
import json

import pytest

from llm_cli.webapi.streams import EventHub


@pytest.mark.webapi
@pytest.mark.asyncio
async def test_event_hub_delivers_to_subscribers():
    hub = EventHub[dict]()

    received = []
    sub = hub.subscribe()

    async def consume():
        async for ev in sub.events(timeout=0.5):
            received.append(ev)
            if len(received) == 2:
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    hub.publish({"v": 1})
    hub.publish({"v": 2})
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [{"v": 1}, {"v": 2}]


@pytest.mark.webapi
@pytest.mark.asyncio
async def test_event_hub_multiple_subscribers_each_get_all_events():
    hub = EventHub[int]()
    s1, s2 = hub.subscribe(), hub.subscribe()
    out1, out2 = [], []

    async def drain(sub, out):
        async for ev in sub.events(timeout=0.5):
            out.append(ev)
            if len(out) == 3:
                break

    t1 = asyncio.create_task(drain(s1, out1))
    t2 = asyncio.create_task(drain(s2, out2))
    await asyncio.sleep(0.05)
    for i in range(3):
        hub.publish(i)
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
    assert out1 == [0, 1, 2]
    assert out2 == [0, 1, 2]
```

Add `asyncio` to test deps: in `pyproject.toml [project.optional-dependencies] dev`, add `pytest-asyncio>=0.23`. Also set `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`. (Run `uv pip install -e ".[dev,dashboard]"` again.)

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
"""In-process event hubs + SSE helpers."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Generic, TypeVar

T = TypeVar("T")


class _Subscription(Generic[T]):
    def __init__(self) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=1024)
        self._closed = False

    async def events(self, *, timeout: float | None = None) -> AsyncIterator[T]:
        while not self._closed:
            try:
                if timeout is None:
                    item = await self._queue.get()
                else:
                    item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return
            yield item

    def close(self) -> None:
        self._closed = True

    def _publish(self, item: T) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            # Drop oldest to keep up.
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(item)
            except asyncio.QueueFull:
                pass


class EventHub(Generic[T]):
    def __init__(self) -> None:
        self._subs: list[_Subscription[T]] = []

    def subscribe(self) -> _Subscription[T]:
        s = _Subscription[T]()
        self._subs.append(s)
        return s

    def publish(self, item: T) -> None:
        for s in self._subs:
            s._publish(item)

    def unsubscribe(self, sub: _Subscription[T]) -> None:
        sub.close()
        if sub in self._subs:
            self._subs.remove(sub)
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/webapi/streams.py tests/webapi/test_streams.py pyproject.toml
git commit -m "feat(webapi): in-process EventHub for SSE fan-out"
```

---

### Task 10: `webapi/static.py` — SPA serving with fallback

**Files:**
- Create: `src/llm_cli/webapi/static.py`
- Modify: `tests/webapi/test_routes_health_version.py` (created in Task 11; this task's tests piggyback)

Behavior: mount `dashboard/dist/` at `/`; for any path that doesn't match a file, return `index.html` (so client-side routing works on hard refresh). If `dashboard/dist/` does not exist, mount returns 503 for all non-`/api/*` paths with a helpful "run `loco dashboard install`" message.

- [ ] **Step 1: Implement (no separate tests — integration tested in Task 11)**

```python
"""SPA static serving for dashboard/dist with index.html fallback."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """StaticFiles with index.html fallback for unknown paths."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def mount_spa(app: FastAPI, dist_dir: Path) -> None:
    if not dist_dir.is_dir() or not (dist_dir / "index.html").is_file():
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _not_installed(full_path: str, request: Request):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="not found")
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "DASHBOARD_NOT_BUILT",
                        "message": "Dashboard frontend not built. Run `loco dashboard install`.",
                        "details": {"dist_dir": str(dist_dir)},
                        "fix_hint": "Run `loco dashboard install`",
                    }
                },
            )
        return

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="spa")
```

- [ ] **Step 2: Commit (no test in this task — covered by Task 11 integration test)**

```bash
git add src/llm_cli/webapi/static.py
git commit -m "feat(webapi): SPA serving with index.html fallback and not-built JSON 503"
```

---

### Task 11: `webapi/app.py` — `create_app()` factory + `/api/health` + `/api/version`

**Files:**
- Create: `src/llm_cli/webapi/app.py`
- Create: `src/llm_cli/webapi/deps.py`
- Create: `src/llm_cli/webapi/routes/__init__.py`
- Create: `src/llm_cli/webapi/routes/health.py`
- Create: `src/llm_cli/webapi/routes/version.py`
- Create: `tests/webapi/test_routes_health_version.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from fastapi.testclient import TestClient

from llm_cli.webapi.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    # Force an empty dist_dir so SPA fallback yields 503 for /
    monkeypatch.setattr("llm_cli.webapi.app._dist_dir", lambda: tmp_path / "empty-dist")
    app = create_app(allowed_hosts={"testserver"})
    return TestClient(app)


@pytest.mark.webapi
def test_health_returns_ok(client):
    r = client.get("/api/health", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.webapi
def test_version_returns_cli_version(client):
    r = client.get("/api/version", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert "cli_version" in body
    assert isinstance(body["cli_version"], str)


@pytest.mark.webapi
def test_spa_not_built_yields_503(client):
    r = client.get("/", headers={"Host": "testserver"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "DASHBOARD_NOT_BUILT"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

`src/llm_cli/webapi/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["meta"])
def health():
    return {"ok": True}
```

`src/llm_cli/webapi/routes/version.py`:

```python
from fastapi import APIRouter

from llm_cli.core import dashboard as dash
from llm_cli.core.versions import current_cli_version

router = APIRouter()


@router.get("/version", tags=["meta"])
def version():
    record = dash.load_installed_record()
    return {
        "cli_version": current_cli_version(),
        "dashboard_installed_cli_version": record.cli_version if record else None,
        "dashboard_installed_at": record.installed_at if record else None,
    }
```

(If `core/versions.py` doesn't have `current_cli_version()`, add it — read `__version__` from `pyproject.toml` via `importlib.metadata.version("loco-llm-cli")`.)

`src/llm_cli/webapi/deps.py`:

```python
"""Shared FastAPI dependencies (no DB sessions in v1, but a hook point)."""
from __future__ import annotations
```

`src/llm_cli/webapi/app.py`:

```python
"""FastAPI app factory."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_cli.core import dashboard as dash
from llm_cli.webapi.errors import install_exception_handlers
from llm_cli.webapi.middleware import (
    HostHeaderMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from llm_cli.webapi.routes import health, version
from llm_cli.webapi.static import mount_spa


def _dist_dir() -> Path:
    return dash.dist_dir()


def create_app(*, allowed_hosts: set[str], cors_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(
        title="LocalLLM Dashboard API",
        version="0.1.0",
        docs_url=None,  # disable Swagger UI in v1 (CSP'd anyway)
        redoc_url=None,
    )

    install_exception_handlers(app)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or [],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(HostHeaderMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(RequestIDMiddleware)

    api = FastAPI(title="api")
    api.include_router(health.router)
    api.include_router(version.router)
    app.mount("/api", api)

    mount_spa(app, _dist_dir())
    return app
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/webapi/app.py src/llm_cli/webapi/deps.py \
        src/llm_cli/webapi/routes/__init__.py \
        src/llm_cli/webapi/routes/health.py src/llm_cli/webapi/routes/version.py \
        tests/webapi/test_routes_health_version.py
git commit -m "feat(webapi): FastAPI factory + health + version routes + middleware wiring"
```

---

### Task 12: `webapi/export_openapi.py` + `scripts/regen-api-client.sh`

**Files:**
- Create: `src/llm_cli/webapi/export_openapi.py`
- Create: `scripts/regen-api-client.sh`

- [ ] **Step 1: Implement the exporter**

```python
"""`python -m llm_cli.webapi.export_openapi` → stdout."""
from __future__ import annotations

import json
import sys

from llm_cli.webapi.app import create_app


def main() -> int:
    app = create_app(allowed_hosts={"127.0.0.1:7878"})
    schema = app.openapi()
    # Strip server-specific noise that would create churn:
    schema.get("info", {}).pop("version", None)
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement the regen script**

`scripts/regen-api-client.sh`:

```bash
#!/usr/bin/env bash
# Regenerate dashboard/src/api/generated.ts from FastAPI's exported OpenAPI schema.
#
#   scripts/regen-api-client.sh          # write/update generated.ts
#   scripts/regen-api-client.sh --check  # exit non-zero if the file would change
set -euo pipefail

cd "$(dirname "$0")/.."

OUT=dashboard/src/api/generated.ts
TMP_SCHEMA=$(mktemp)
TMP_OUT=$(mktemp)
trap 'rm -f "$TMP_SCHEMA" "$TMP_OUT"' EXIT

python -m llm_cli.webapi.export_openapi > "$TMP_SCHEMA"

if ! command -v npx >/dev/null 2>&1; then
  echo "regen-api-client: npx not found; install Node.js 20+." >&2
  exit 2
fi

(cd dashboard && npx --yes openapi-typescript@7 "../$TMP_SCHEMA" -o "../$TMP_OUT")

if [[ "${1:-}" == "--check" ]]; then
  if ! diff -u "$OUT" "$TMP_OUT" >/dev/null 2>&1; then
    echo "API client out of date. Run: scripts/regen-api-client.sh" >&2
    diff -u "$OUT" "$TMP_OUT" || true
    exit 1
  fi
  echo "API client is up to date."
  exit 0
fi

mkdir -p "$(dirname "$OUT")"
mv "$TMP_OUT" "$OUT"
echo "Wrote $OUT"
```

Make it executable:

```bash
chmod +x scripts/regen-api-client.sh
```

(Note: this script's `--check` mode requires `dashboard/` to have run `npm ci` at least once locally. CI will install before running. Document this in `dashboard/README.md` in Task 29.)

- [ ] **Step 3: Smoke test (after Tasks 13 + 29 land the deps)**

For now: just verify the exporter runs:

```bash
python -m llm_cli.webapi.export_openapi | head -n 5
```

Expected: prints `{` + `"components": {...}` ish — valid JSON.

- [ ] **Step 4: Commit**

```bash
git add src/llm_cli/webapi/export_openapi.py scripts/regen-api-client.sh
git commit -m "feat(webapi): OpenAPI exporter + regen-api-client.sh with --check mode"
```

---

## Phase C — Install + serve + status + uninstall

### Task 13: Complete `loco dashboard install`

**Files:**
- Modify: `src/llm_cli/commands/dashboard_cmd.py`
- Modify: `src/llm_cli/core/dashboard.py` (add `run_install()`)
- Modify: `tests/unit/test_cli_dashboard.py`

**Behavior:**

1. Resolve current CLI version + repo_root.
2. Unless `--skip-python`: `uv pip install fastapi 'uvicorn[standard]' sse-starlette` into the managed venv (idempotent — uv handles existing).
3. Unless `--skip-frontend`: check `node --version` ≥ 20 and `npm --version`. On missing, print per-platform hint and exit 78.
4. Unless `--skip-frontend`: if `--reset`, `rm -rf dashboard/node_modules`. Then `cd dashboard && npm ci && npm run build`.
5. Read `node --version` and `npm --version` outputs; compute `dist_hash`; write `.installed`.

- [ ] **Step 1: Write the test**

```python
def test_install_writes_installed_record_when_skips_used(tmp_path, monkeypatch):
    """With --skip-python --skip-frontend, install just writes the marker."""
    # Setup a fake dashboard/dist
    repo = tmp_path / "repo"
    (repo / "dashboard" / "dist").mkdir(parents=True)
    (repo / "dashboard" / "dist" / "index.html").write_text("<!doctype html>")

    monkeypatch.setattr(
        "llm_cli.core.settings.resolve_settings",
        lambda: type("S", (), {"data_root": tmp_path, "repo_root": repo,
                               "runtimes_dir": tmp_path, "models_dir": tmp_path,
                               "cache_dir": tmp_path})(),
    )
    monkeypatch.setattr("llm_cli.core.dashboard.dashboard_root", lambda: repo / "dashboard")

    # Stub out node/npm version probing
    monkeypatch.setattr("llm_cli.core.dashboard._probe_node_version", lambda: "20.11.1")
    monkeypatch.setattr("llm_cli.core.dashboard._probe_npm_version", lambda: "10.2.4")

    result = runner.invoke(app, ["dashboard", "install", "--skip-python", "--skip-frontend"])
    assert result.exit_code == 0, result.stdout

    record = (repo / "dashboard" / ".installed").read_text()
    assert "node_version: 20.11.1" in record
    assert "npm_version: 10.2.4" in record
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `run_install()` in `core/dashboard.py`**

Append to `core/dashboard.py`:

```python
import shutil
import subprocess
from datetime import UTC, datetime


def _probe_node_version() -> str:
    try:
        out = subprocess.check_output(["node", "--version"], text=True).strip()
        return out.lstrip("v")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise RuntimeError("`node` not found. Install Node.js 20+.") from e


def _probe_npm_version() -> str:
    try:
        return subprocess.check_output(["npm", "--version"], text=True).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise RuntimeError("`npm` not found.") from e


def _check_node_minimum(version: str, minimum: tuple[int, ...] = (20, 0)) -> None:
    parts = tuple(int(p) for p in version.split(".")[:2])
    if parts < minimum:
        raise RuntimeError(f"Node {'.'.join(map(str, minimum))}+ required; found {version}.")


def run_install(
    *,
    cli_version: str,
    skip_python: bool,
    skip_frontend: bool,
    reset: bool,
    venv_python: str = "python",
) -> InstalledRecord:
    """Idempotent install. Returns the freshly-written record."""
    root = dashboard_root()

    if not skip_python:
        subprocess.check_call([
            "uv", "pip", "install",
            "fastapi>=0.115,<1.0",
            "uvicorn[standard]>=0.30,<1.0",
            "sse-starlette>=2.1,<3.0",
        ])

    if not skip_frontend:
        node_v = _probe_node_version()
        _check_node_minimum(node_v)
        npm_v = _probe_npm_version()

        if reset:
            shutil.rmtree(root / "node_modules", ignore_errors=True)

        subprocess.check_call(["npm", "ci"], cwd=root)
        subprocess.check_call(["npm", "run", "build"], cwd=root)
    else:
        node_v = _probe_node_version() if shutil.which("node") else "skipped"
        npm_v = _probe_npm_version() if shutil.which("npm") else "skipped"

    d = dist_dir()
    if not (d / "index.html").is_file():
        raise RuntimeError(
            "dashboard/dist/index.html missing after build "
            "(or --skip-frontend used without an existing dist)."
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
```

- [ ] **Step 4: Wire into the Typer command**

In `commands/dashboard_cmd.py`, replace the `install` body:

```python
from llm_cli.core.versions import current_cli_version


@app.command()
def install(
    reset: Annotated[bool, typer.Option("--reset")] = False,
    skip_frontend: Annotated[bool, typer.Option("--skip-frontend")] = False,
    skip_python: Annotated[bool, typer.Option("--skip-python")] = False,
) -> None:
    try:
        record = dash.run_install(
            cli_version=current_cli_version(),
            skip_python=skip_python,
            skip_frontend=skip_frontend,
            reset=reset,
        )
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=78)
    typer.secho(
        f"Dashboard installed (CLI {record.cli_version}, node {record.node_version}, "
        f"npm {record.npm_version}).",
        fg=typer.colors.GREEN,
    )
```

- [ ] **Step 5: Run — PASS**

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/core/dashboard.py src/llm_cli/commands/dashboard_cmd.py tests/unit/test_cli_dashboard.py
git commit -m "feat(dashboard): implement `loco dashboard install` (python deps + npm build + .installed)"
```

---

### Task 14: Complete `loco dashboard serve` (background + foreground)

**Files:**
- Modify: `src/llm_cli/commands/dashboard_cmd.py`
- Modify: `src/llm_cli/core/dashboard.py` (add `start_server()`, `stop_server()`)

**Behavior:**

- `--foreground`: `uvicorn.run(create_app(allowed_hosts={...}), host=..., port=...)` in-process; SIGINT cleans up PID file.
- Default (background): spawn detached subprocess `uvicorn llm_cli.webapi.app:create_app --factory --host ... --port ...` with stdout/stderr to `state/dashboard/server.log`; write PID to `state/dashboard/server.pid`; poll `GET /api/health` until 200 OK or 30s timeout; auto-open browser unless `--no-open`.
- Refuses if `verify_installed()` is not `("ok", _)` — prints the verdict and a remediation hint.
- Refuses if `--host` is not `127.0.0.1` or `localhost` (Plan 5 will add `--insecure` handling).

- [ ] **Step 1: Write the test**

```python
def test_serve_refuses_when_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "llm_cli.core.settings.resolve_settings",
        lambda: type("S", (), {"data_root": tmp_path, "repo_root": tmp_path,
                               "runtimes_dir": tmp_path, "models_dir": tmp_path,
                               "cache_dir": tmp_path})(),
    )
    result = runner.invoke(app, ["dashboard", "serve"])
    assert result.exit_code != 0
    assert "install" in result.stdout.lower() or "install" in (result.stderr or "").lower()


def test_serve_refuses_non_localhost_host():
    result = runner.invoke(app, ["dashboard", "serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0
    assert "--insecure" in (result.stdout + (result.stderr or ""))
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Add server-control helpers to `core/dashboard.py`**

```python
import os
import socket
import sys
import time
import webbrowser


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def _allowed_hosts_for(host: str, port: int) -> set[str]:
    return {f"{host}:{port}", f"localhost:{port}", f"127.0.0.1:{port}"}


def start_server_background(host: str, port: int) -> int:
    """Spawn uvicorn detached; return child PID after readiness."""
    if _port_in_use(host, port):
        raise RuntimeError(f"Port {port} already in use on {host}.")

    log_path = server_log_path()
    log_fd = open(log_path, "ab", buffering=0)

    env = os.environ.copy()
    env["LLM_DASHBOARD_ALLOWED_HOSTS"] = ",".join(sorted(_allowed_hosts_for(host, port)))

    cmd = [
        sys.executable, "-m", "uvicorn",
        "llm_cli.webapi.app:create_app", "--factory",
        "--host", host, "--port", str(port),
        "--log-level", "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=log_fd, stderr=log_fd,
        stdin=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    server_pid_path().write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + 30.0
    last_err: str | None = None
    while time.time() < deadline:
        try:
            import httpx
            r = httpx.get(f"http://{host}:{port}/api/health",
                          headers={"Host": f"{host}:{port}"}, timeout=1.0)
            if r.status_code == 200 and r.json().get("ok") is True:
                return proc.pid
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        if proc.poll() is not None:
            raise RuntimeError(
                f"Dashboard server exited during startup (last error: {last_err}). "
                f"See {log_path} for details."
            )
        time.sleep(0.25)

    proc.terminate()
    raise RuntimeError(f"Dashboard server did not become ready within 30s (last: {last_err}).")


def run_server_foreground(host: str, port: int) -> None:
    """Run uvicorn in-process; blocks until SIGINT/SIGTERM."""
    import uvicorn

    server_pid_path().write_text(str(os.getpid()), encoding="utf-8")
    env_key = "LLM_DASHBOARD_ALLOWED_HOSTS"
    os.environ[env_key] = ",".join(sorted(_allowed_hosts_for(host, port)))
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
    """Send SIGTERM, escalate to SIGKILL. Returns True if a server was stopped."""
    pid = read_server_pid()
    if pid is None:
        return False
    if not is_server_alive(pid):
        try:
            server_pid_path().unlink()
        except FileNotFoundError:
            pass
        return False
    import signal
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
        except (ProcessLookupError, PermissionError):
            pass
    try:
        server_pid_path().unlink()
    except FileNotFoundError:
        pass
    return True


def open_browser(host: str, port: int) -> None:
    try:
        webbrowser.open(f"http://{host}:{port}/")
    except Exception:
        pass  # best-effort
```

- [ ] **Step 4: Update `create_app` to read allowed_hosts from env when called as a factory**

In `webapi/app.py`, change the factory call (used by `uvicorn --factory`) to read from env:

```python
import os


def create_app(
    *,
    allowed_hosts: set[str] | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    if allowed_hosts is None:
        env_val = os.environ.get("LLM_DASHBOARD_ALLOWED_HOSTS", "127.0.0.1:7878,localhost:7878")
        allowed_hosts = {h.strip() for h in env_val.split(",") if h.strip()}
    if cors_origins is None:
        cors_origins = [f"http://{h}" for h in allowed_hosts] + [
            "http://127.0.0.1:5173", "http://localhost:5173",
        ]
    # ... rest unchanged
```

- [ ] **Step 5: Wire into Typer**

Replace `serve` body in `dashboard_cmd.py`:

```python
_LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port")] = 7878,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    foreground: Annotated[bool, typer.Option("--foreground")] = False,
    no_open: Annotated[bool, typer.Option("--no-open")] = False,
) -> None:
    if host not in _LOCALHOST_HOSTS:
        typer.secho(
            f"Refusing to bind to {host}. Non-localhost binding requires --insecure "
            "(planned for the security-hardening release).",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=78)

    verdict, reason = dash.verify_installed(current_cli_version())
    if verdict != "ok":
        typer.secho(
            f"Dashboard is not ready ({verdict}): {reason}. "
            "Run `loco dashboard install`"
            + (" --reset" if verdict in ("version_mismatch", "hash_mismatch") else "")
            + ".",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=78)

    if foreground:
        typer.echo(f"Starting dashboard on http://{host}:{port}/ (foreground; Ctrl-C to stop)")
        if not no_open:
            dash.open_browser(host, port)
        dash.run_server_foreground(host, port)
        return

    try:
        pid = dash.start_server_background(host, port)
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"Dashboard started on http://{host}:{port}/ (pid {pid})", fg=typer.colors.GREEN)
    if not no_open:
        dash.open_browser(host, port)
```

- [ ] **Step 6: Run — PASS**

- [ ] **Step 7: Commit**

```bash
git add src/llm_cli/core/dashboard.py src/llm_cli/commands/dashboard_cmd.py \
        src/llm_cli/webapi/app.py tests/unit/test_cli_dashboard.py
git commit -m "feat(dashboard): `loco dashboard serve` (background + foreground, readiness wait, browser auto-open)"
```

---

### Task 15: `loco dashboard stop` + `uninstall` (final wiring)

**Files:**
- Modify: `src/llm_cli/commands/dashboard_cmd.py`

- [ ] **Step 1: Write tests**

```python
def test_stop_when_no_server_running(monkeypatch):
    monkeypatch.setattr("llm_cli.core.dashboard.read_server_pid", lambda: None)
    result = runner.invoke(app, ["dashboard", "stop"])
    assert result.exit_code == 0
    assert "not running" in result.stdout.lower() or "no server" in result.stdout.lower()


def test_uninstall_removes_marker(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "dashboard").mkdir(parents=True)
    (repo / "dashboard" / ".installed").write_text("cli_version: '1.1.0'\n")
    monkeypatch.setattr("llm_cli.core.dashboard.dashboard_root", lambda: repo / "dashboard")
    result = runner.invoke(app, ["dashboard", "uninstall"])
    assert result.exit_code == 0
    assert not (repo / "dashboard" / ".installed").exists()
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
@app.command()
def stop() -> None:
    if dash.stop_server():
        typer.echo("Dashboard stopped.")
    else:
        typer.echo("No dashboard server is running.")


@app.command()
def uninstall(
    purge: Annotated[bool, typer.Option("--purge")] = False,
) -> None:
    marker = dash.installed_marker_path()
    if marker.exists():
        marker.unlink()
    if purge:
        import shutil
        shutil.rmtree(dash.dist_dir(), ignore_errors=True)
        shutil.rmtree(dash.dashboard_root() / "node_modules", ignore_errors=True)
        typer.echo("Removed .installed, dist/, and node_modules/.")
    else:
        typer.echo("Removed .installed (use --purge to also delete dist/ and node_modules/).")
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/dashboard_cmd.py tests/unit/test_cli_dashboard.py
git commit -m "feat(dashboard): implement `loco dashboard stop` and `uninstall [--purge]`"
```

---

### Task 16: `loco doctor dashboard` scope

**Files:**
- Modify: `src/llm_cli/core/doctor.py`
- Modify: `src/llm_cli/commands/doctor.py`
- Create: `tests/unit/test_doctor_dashboard_scope.py`

- [ ] **Step 1: Inspect the existing doctor scope dispatcher**

```bash
grep -n "scope" src/llm_cli/core/doctor.py src/llm_cli/commands/doctor.py
```

Identify the function that maps `--scope dashboard` → checks-to-run.

- [ ] **Step 2: Write the failing test**

```python
import pytest

from llm_cli.core import doctor as docmod


def test_dashboard_scope_reports_node_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: None if cmd in ("node", "npm") else "/usr/bin/x")
    results = docmod.run_scope("dashboard")
    by_name = {r.name: r for r in results}
    assert by_name["node"].status in {"error", "warning"}
    assert by_name["npm"].status in {"error", "warning"}


def test_dashboard_scope_reports_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr("llm_cli.core.dashboard.load_installed_record", lambda: None)
    results = docmod.run_scope("dashboard")
    by_name = {r.name: r for r in results}
    assert by_name["dashboard installed"].status == "info"
```

(Adapt to match the actual `Result`/`Check` shape `core/doctor.py` uses.)

- [ ] **Step 3: Run — FAIL**

- [ ] **Step 4: Implement**

Add to `core/doctor.py`:

```python
def _dashboard_scope_checks() -> list[CheckResult]:
    """Return CheckResult list for `loco doctor dashboard`."""
    from llm_cli.core import dashboard as dash
    from llm_cli.core.versions import current_cli_version
    import shutil

    results: list[CheckResult] = []
    node = shutil.which("node")
    npm = shutil.which("npm")
    record = dash.load_installed_record()

    results.append(CheckResult(
        name="node",
        status="error" if (node is None and record is not None) else "info" if node is None else "ok",
        message=(
            "Node.js not found (install Node 20+)" if node is None
            else f"Found at {node}"
        ),
    ))
    results.append(CheckResult(
        name="npm",
        status="error" if (npm is None and record is not None) else "info" if npm is None else "ok",
        message="npm not found" if npm is None else f"Found at {npm}",
    ))
    results.append(CheckResult(
        name="dashboard installed",
        status="info" if record is None else "ok",
        message=(
            "Not installed (run `loco dashboard install`)" if record is None
            else f"Installed for CLI {record.cli_version} at {record.installed_at}"
        ),
    ))
    if record is not None:
        cur = current_cli_version()
        results.append(CheckResult(
            name="dashboard version matches CLI",
            status="ok" if record.cli_version == cur else "error",
            message=(
                "Match" if record.cli_version == cur
                else f"Built for CLI {record.cli_version}, current is {cur}. "
                     "Run `loco dashboard install --reset`."
            ),
        ))
        verdict, reason = dash.verify_installed(cur)
        results.append(CheckResult(
            name="dashboard dist integrity",
            status="ok" if verdict == "ok" else "warning",
            message=("OK" if verdict == "ok" else f"{verdict}: {reason}"),
        ))

    pid = dash.read_server_pid()
    if pid is not None:
        results.append(CheckResult(
            name="dashboard server pid alive",
            status="ok" if dash.is_server_alive(pid) else "warning",
            message=(f"pid={pid} alive" if dash.is_server_alive(pid)
                     else f"Stale pid file (pid={pid}); run `loco dashboard stop`."),
        ))

    return results
```

And register the new scope in whatever `SCOPES` map / dispatcher exists. Then in `commands/doctor.py`, add `"dashboard"` to the accepted `--scope` values (or `dashboard` as a subcommand if that's the existing pattern).

- [ ] **Step 5: Run — PASS**

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/core/doctor.py src/llm_cli/commands/doctor.py tests/unit/test_doctor_dashboard_scope.py
git commit -m "feat(doctor): add `dashboard` scope (node/npm, install record, dist integrity, server pid)"
```

---

### Task 17: `loco setup` chain — opt-in dashboard step

**Files:**
- Modify: `src/llm_cli/commands/setup.py`
- Modify: relevant test files for setup chain

- [ ] **Step 1: Read existing setup chain**

```bash
grep -n "step\|chain\|y/n\|prompt" src/llm_cli/commands/setup.py | head -n 40
```

Identify how the existing optional steps (runtime/model/config/serve) are sequenced.

- [ ] **Step 2: Write the failing test**

In an existing setup test file (or new `tests/unit/test_setup_chain.py`):

```python
def test_setup_chain_offers_dashboard_step(monkeypatch, tmp_path):
    """The setup chain should offer to install the dashboard last, default No."""
    # Use whatever fixture pattern the existing setup tests use to drive the chain
    # and assert that "dashboard" appears in the prompts and is skipped on default.
    ...
```

(Pattern after `tests/unit/test_setup*.py` if present.)

- [ ] **Step 3: Implement**

In `setup.py`, after the existing optional `serve` step in the chain, add:

```python
from llm_cli.commands.dashboard_cmd import install as _dashboard_install


def _maybe_install_dashboard(noninteractive: bool) -> None:
    if noninteractive:
        return
    if not questionary.confirm(
        "Install the web dashboard now?", default=False
    ).ask():
        typer.echo("Skipped dashboard install. You can run `loco dashboard install` later.")
        return
    try:
        _dashboard_install()  # delegates to the Typer command's logic
    except typer.Exit as e:
        if e.exit_code != 0:
            typer.secho(
                "Dashboard install failed; continuing setup. "
                "Run `loco dashboard install` to retry.",
                fg=typer.colors.YELLOW,
            )
```

Wire `_maybe_install_dashboard(...)` into the chain after the existing steps.

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/setup.py tests/unit/test_setup*
git commit -m "feat(setup): offer optional dashboard install at end of `loco setup` chain"
```

---

### Task 18: `loco update` — auto-rebuild dashboard if installed

**Files:**
- Modify: `src/llm_cli/commands/update_cmd.py`
- Modify: relevant update tests

- [ ] **Step 1: Read existing update flow**

```bash
grep -n "post\|after\|hook\|run_install" src/llm_cli/commands/update_cmd.py
```

Find the spot after the git pull / dep sync where additional post-update hooks can run.

- [ ] **Step 2: Write the failing test**

```python
def test_update_rebuilds_dashboard_if_installed(monkeypatch, tmp_path):
    """When dashboard/.installed shows a previous CLI version, update auto-rebuilds."""
    called = {"install": False}
    monkeypatch.setattr("llm_cli.core.dashboard.load_installed_record",
                        lambda: type("R", (), {"cli_version": "0.9.0"})())
    monkeypatch.setattr("llm_cli.core.versions.current_cli_version", lambda: "1.1.0")

    def fake_install(**kwargs):
        called["install"] = True
        return type("R", (), {"cli_version": "1.1.0", "node_version": "20", "npm_version": "10"})()

    monkeypatch.setattr("llm_cli.core.dashboard.run_install", fake_install)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/" + cmd)

    from llm_cli.commands.update_cmd import _post_update_hooks
    _post_update_hooks()
    assert called["install"] is True


def test_update_skips_dashboard_rebuild_if_node_missing(monkeypatch):
    monkeypatch.setattr("llm_cli.core.dashboard.load_installed_record",
                        lambda: type("R", (), {"cli_version": "0.9.0"})())
    monkeypatch.setattr("llm_cli.core.versions.current_cli_version", lambda: "1.1.0")
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    # Should NOT raise
    from llm_cli.commands.update_cmd import _post_update_hooks
    _post_update_hooks()
```

- [ ] **Step 3: Run — FAIL**

- [ ] **Step 4: Implement**

In `update_cmd.py`, add:

```python
def _post_update_hooks() -> None:
    """Run opportunistic post-update actions (idempotent, must not crash)."""
    import shutil
    from llm_cli.core import dashboard as dash
    from llm_cli.core.versions import current_cli_version

    record = dash.load_installed_record()
    if record is None:
        return
    if record.cli_version == current_cli_version():
        return
    if not shutil.which("node") or not shutil.which("npm"):
        typer.secho(
            "Dashboard is installed but node/npm not found; skipping rebuild. "
            "Run `loco dashboard install` after installing Node 20+.",
            fg=typer.colors.YELLOW,
        )
        return
    try:
        dash.run_install(
            cli_version=current_cli_version(),
            skip_python=False, skip_frontend=False, reset=False,
        )
        typer.echo("Dashboard rebuilt to match new CLI version.")
    except Exception as e:
        typer.secho(f"Dashboard rebuild failed: {e}", fg=typer.colors.YELLOW)
```

Call `_post_update_hooks()` at the end of the existing update flow.

- [ ] **Step 5: Run — PASS**

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/commands/update_cmd.py tests/unit/test_update*
git commit -m "feat(update): rebuild dashboard after `loco update` when version drifts (best-effort)"
```

---

## Phase D — Read-only routes

For each of Tasks 19–27, follow the same pattern:

1. Write the failing test(s) in `tests/webapi/test_routes_<name>.py`.
2. Run — verify FAIL.
3. Implement the route in `src/llm_cli/webapi/routes/<name>.py`, register it on the `api` sub-app in `webapi/app.py`.
4. Run — verify PASS.
5. Commit.

### Task 19: `routes/runtimes.py` (GET-only)

**Endpoints:**
- `GET /api/runtimes` → `list[RuntimeSummary]`
- `GET /api/runtimes/{id}` → `RuntimeDetail`

**Schemas (Pydantic):**

```python
from pydantic import BaseModel


class RuntimeSummary(BaseModel):
    id: str
    kind: str
    installed: bool
    installed_at: str | None
    has_metrics: bool  # always False in Plan 1 (no manifest metrics block yet)


class RuntimeDetail(BaseModel):
    id: str
    kind: str
    manifest: dict
    installed: bool
    install_record: dict | None
    drift: dict | None
```

**Test outline:**

```python
@pytest.mark.webapi
def test_list_runtimes_includes_seeded(test_client, seed_runtime):
    seed_runtime("dummy", kind="custom")
    r = test_client.get("/api/runtimes", headers={"Host": "testserver"})
    assert r.status_code == 200
    ids = [rt["id"] for rt in r.json()]
    assert "dummy" in ids


@pytest.mark.webapi
def test_get_runtime_detail_404_when_missing(test_client):
    r = test_client.get("/api/runtimes/does-not-exist", headers={"Host": "testserver"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RUNTIME_NOT_FOUND"
```

(Use existing `tests/conftest.py` fixtures to seed runtimes if available; otherwise add `seed_runtime` helper to `tests/webapi/conftest.py`.)

**Implementation:**

```python
from fastapi import APIRouter

from llm_cli.core import registry, install_record
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


@router.get("/runtimes", response_model=list[RuntimeSummary])
def list_runtimes():
    out = []
    for rt in registry.list_runtimes():
        rec = install_record.read(rt.id)
        out.append(RuntimeSummary(
            id=rt.id, kind=rt.kind,
            installed=rec is not None,
            installed_at=rec.installed_at if rec else None,
            has_metrics=False,
        ))
    return out


@router.get("/runtimes/{runtime_id}", response_model=RuntimeDetail)
def get_runtime(runtime_id: str):
    try:
        rt = registry.get_runtime(runtime_id)
    except KeyError:
        raise ApiError(ErrorCode.RUNTIME_NOT_FOUND, f"Runtime '{runtime_id}' not found",
                       details={"runtime_id": runtime_id}, status_code=404)
    rec = install_record.read(runtime_id)
    return RuntimeDetail(
        id=rt.id, kind=rt.kind, manifest=rt.manifest_dict(),
        installed=rec is not None,
        install_record=rec.as_dict() if rec else None,
        drift=registry.compute_drift(runtime_id) if rec else None,
    )
```

(Method names on `registry`/`install_record` — adapt to existing API. If a method doesn't exist, extract it from the matching `commands/*` file into `core/*` as a sub-step.)

**Commit:** `feat(webapi): GET /api/runtimes and /api/runtimes/{id}`

---

### Task 20: `routes/models.py` (GET-only)

**Endpoints:**
- `GET /api/models`
- `GET /api/models/{id}`

Mirror the runtimes pattern: list calls `model_registry.list_models()`; detail returns full registry entry; 404 maps to `ErrorCode.MODEL_NOT_FOUND`.

**Commit:** `feat(webapi): GET /api/models and /api/models/{id}`

---

### Task 21: `routes/configs.py` (GET-only, with /params endpoint)

**Endpoints:**
- `GET /api/configs` → list
- `GET /api/configs/{id}` → detail with `${data_root}` expansion
- `GET /api/configs/{id}/params` → ParamCell list (read-only for Plan 1)
- `GET /api/configs/{id}/validate` → `{valid: bool, errors: list[str]}`

**Notes:**

- `params` returns the same `ParamCell[]` shape `core/param_grid_models.py` produces. The React Plan 1 just renders this as a read-only YAML preview; Plan 3 wires it to the interactive grid.
- `validate` calls `core/registry.validate_config(id)` (extract from `commands/config_cmd.py` if needed).

**Commit:** `feat(webapi): GET configs (list, detail, params, validate)`

---

### Task 22: `routes/instance.py` (GET + SSE)

**Endpoints:**
- `GET /api/instance` → current `state/running.json` contents or `{running: false}`
- `GET /api/instance/stream` → SSE; pushes the same payload on lifecycle events + every 5s heartbeat
- `GET /api/instance/logs/stream` → SSE; tails `state/logs/<current-config>.log` line-by-line (250ms polling)

**Implementation notes:**

- The lifecycle SSE hub publishes on lifecycle changes. Source: `core/lifecycle.py` (extract publish call as a small refactor) — or, in Plan 1, just poll `state/running.json` mtime every 1s and re-publish on change.
- The logs stream uses a `tail -f`-style polling reader (`f.seek(0, os.SEEK_END)` on open, then poll for new lines).
- If nothing is running, `logs/stream` immediately closes the connection with a `data: {"error":"INSTANCE_NOT_RUNNING"}\n\n` event.

**Tests:**

```python
@pytest.mark.webapi
def test_instance_returns_not_running_when_no_state(test_client, tmp_path):
    r = test_client.get("/api/instance", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"running": False}


@pytest.mark.webapi
def test_instance_stream_yields_initial_snapshot(test_client):
    with test_client.stream("GET", "/api/instance/stream",
                            headers={"Host": "testserver", "Accept": "text/event-stream"},
                            timeout=2.0) as r:
        assert r.status_code == 200
        first_chunk = next(r.iter_text(chunk_size=256))
        assert "data:" in first_chunk
```

**Commit:** `feat(webapi): GET /api/instance + SSE state + SSE logs (read-only)`

---

### Task 23: `routes/doctor.py`

**Endpoint:**
- `GET /api/doctor` → `{scopes: {default: [...], runtime: [...], dashboard: [...]}}`

Each scope's value is a list of check results in the same shape `core/doctor.py` returns.

**Tests:**

```python
@pytest.mark.webapi
def test_doctor_returns_all_scopes(test_client):
    r = test_client.get("/api/doctor", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["scopes"]) >= {"default", "runtime", "dashboard"}
```

**Implementation:**

```python
@router.get("/doctor")
def doctor():
    from llm_cli.core import doctor as docmod
    return {
        "scopes": {
            scope: [r.as_dict() for r in docmod.run_scope(scope)]
            for scope in ("default", "runtime", "dashboard")
        }
    }
```

**Commit:** `feat(webapi): GET /api/doctor with all scopes`

---

### Task 24: `routes/settings.py` (GET-only)

**Endpoint:**
- `GET /api/settings` → `{stored: {...}, resolved: {...}, registry: [{key, kind, required, description}, ...]}`

**Implementation:**

```python
from llm_cli.core.settings import KEY_REGISTRY, load_settings, resolve_settings


@router.get("/settings")
def get_settings():
    resolved = resolve_settings()
    return {
        "stored": load_settings(),
        "resolved": {
            "data_root": str(resolved.data_root),
            "repo_root": str(resolved.repo_root) if resolved.repo_root else None,
            "runtimes_dir": str(resolved.runtimes_dir),
            "models_dir": str(resolved.models_dir),
            "cache_dir": str(resolved.cache_dir),
        },
        "registry": [
            {"key": k, **{kk: vv for kk, vv in v.items() if kk != "default"}}
            for k, v in KEY_REGISTRY.items()
        ],
    }
```

**Commit:** `feat(webapi): GET /api/settings (stored + resolved + registry)`

---

### Task 25: `routes/disk.py`

**Endpoint:**
- `GET /api/disk` → `DiskReport` from `core/disk.scan()`

Direct call; very small wrapper.

**Tests:** seed a fake data_root, assert response includes models + bytes + cache_bytes.

**Commit:** `feat(webapi): GET /api/disk`

---

### Task 26: `routes/history.py` (GET + SSE)

**Endpoints:**
- `GET /api/history?limit=25&offset=0&action=&config_id=&since=&until=` → paginated entries
- `GET /api/history/stream` → SSE pushing new entries as `history.jsonl` grows

**Implementation notes:**

- The list endpoint reads + filters `state/history.jsonl` (use `core/lifecycle.read_history()` if it exists; else add).
- The stream endpoint tails `history.jsonl`; same polling-tail mechanism as `instance/logs/stream`.

**Commit:** `feat(webapi): GET /api/history + SSE history stream`

---

### Task 27: `routes/overview.py`

**Endpoint:**
- `GET /api/overview` → aggregate payload used by the Overview page

Schema:

```python
class Overview(BaseModel):
    version: dict          # from /api/version
    instance: dict         # current running.json or {running: false}
    runtimes_count: int
    runtimes_installed_count: int
    models_count: int
    configs_count: int
    doctor_summary: dict   # {default: {error, warning, ok}, runtime: {...}, dashboard: {...}}
    recent_history: list[dict]  # last 5 entries
    disk_summary: dict     # {data_root_pct_used, models_count, cache_bytes}
```

Pure aggregation — no new core logic, just composition of existing endpoints' data.

**Commit:** `feat(webapi): GET /api/overview aggregate`

---

## Phase E — React scaffolding

### Task 28: Scaffold `dashboard/` (Vite + React + TS + Tailwind v4 + shadcn init)

**Files:**
- Create: all `dashboard/*` config files listed in the file map

- [ ] **Step 1: Initialize Vite + React + TS in `dashboard/`**

```bash
mkdir -p dashboard
cd dashboard
npm create vite@latest . -- --template react-ts -y
```

This creates `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`.

- [ ] **Step 2: Install runtime dependencies**

```bash
npm install \
  @tanstack/react-query@^5 \
  @tanstack/react-router@^1 \
  zustand@^5 \
  sonner@^1 \
  clsx@^2 \
  class-variance-authority@^0.7 \
  tailwind-merge@^2 \
  lucide-react@^0.400
```

- [ ] **Step 3: Install Tailwind v4**

```bash
npm install -D tailwindcss@^4 @tailwindcss/vite@^4 postcss@^8 autoprefixer@^10
```

Update `vite.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:7878', changeOrigin: false },
    },
  },
})
```

Update `dashboard/src/styles/globals.css`:

```css
@import "tailwindcss";

@layer base {
  :root { color-scheme: light; }
  body { @apply bg-zinc-50 text-zinc-900 antialiased; }
}
```

Import `globals.css` in `dashboard/src/main.tsx`.

- [ ] **Step 4: shadcn init**

```bash
npx shadcn@latest init -y -d
```

Choose: TypeScript, default style, zinc base color, CSS variables: yes. This writes `components.json` and updates `tsconfig.json`.

Install the primitives we'll use throughout:

```bash
npx shadcn@latest add button card badge table tabs input dropdown-menu \
                       sheet sonner separator skeleton tooltip
```

- [ ] **Step 5: Install dev deps**

```bash
npm install -D \
  vitest@^2 @vitest/ui@^2 \
  @testing-library/react@^16 \
  @testing-library/jest-dom@^6 \
  jsdom@^25 \
  msw@^2 \
  @types/node@^22
```

Add to `dashboard/package.json` scripts:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "typecheck": "tsc --noEmit",
  "test": "vitest run",
  "test:watch": "vitest",
  "regen-client": "../scripts/regen-api-client.sh"
}
```

- [ ] **Step 6: Verify build works**

```bash
npm run build
```

Expected: `dist/index.html` + `dist/assets/*` produced without errors.

- [ ] **Step 7: Commit**

```bash
git add dashboard/
git commit -m "feat(dashboard): scaffold Vite + React 19 + TS + Tailwind v4 + shadcn/ui"
```

---

### Task 29: TanStack Router + Query + Zustand + sonner wiring

**Files:**
- Modify: `dashboard/src/main.tsx`
- Create: `dashboard/src/router.tsx`
- Create: `dashboard/src/queryClient.ts`
- Create: `dashboard/src/store.ts`

- [ ] **Step 1: queryClient.ts**

```ts
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})
```

- [ ] **Step 2: store.ts (Zustand)**

```ts
import { create } from 'zustand'

interface AppStore {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  jobsTrayOpen: boolean
  setJobsTrayOpen: (open: boolean) => void
}

export const useAppStore = create<AppStore>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  jobsTrayOpen: false,
  setJobsTrayOpen: (open) => set({ jobsTrayOpen: open }),
}))
```

- [ ] **Step 3: router.tsx — placeholder route tree (pages added in later tasks)**

```tsx
import { createRouter, createRootRoute, createRoute, Outlet } from '@tanstack/react-router'
import { Layout } from '@/components/Layout'

const rootRoute = createRootRoute({ component: () => <Layout><Outlet /></Layout> })

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => <div>Overview (Task 34)</div>,
})

const routeTree = rootRoute.addChildren([overviewRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}
```

- [ ] **Step 4: main.tsx — wire everything**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { queryClient } from './queryClient'
import { router } from './router'
import './styles/globals.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster position="top-right" richColors closeButton />
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 5: Verify dev server works**

```bash
npm run dev
```

(Manually open `http://localhost:5173/`, expect to see "Overview (Task 34)".)

- [ ] **Step 6: Commit**

```bash
git add dashboard/
git commit -m "feat(dashboard): wire TanStack Router/Query, Zustand store, sonner toaster"
```

---

### Task 30: Generate OpenAPI TypeScript client (initial)

- [ ] **Step 1: Run the regen script**

```bash
scripts/regen-api-client.sh
```

Expected: writes `dashboard/src/api/generated.ts`.

- [ ] **Step 2: Create the thin wrapper**

`dashboard/src/api/client.ts`:

```ts
import createClient from 'openapi-fetch'
import type { paths } from './generated'

export const api = createClient<paths>({ baseUrl: '/api' })
```

(Install `openapi-fetch` if not present: `npm install openapi-fetch@^0.11`.)

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/api/ dashboard/package.json dashboard/package-lock.json
git commit -m "feat(dashboard): typed API client generated from OpenAPI schema"
```

---

### Task 31: App shell — Layout, Header, Sidebar, SecurityBanner

**Files:**
- Create: `dashboard/src/components/Layout.tsx`
- Create: `dashboard/src/components/Header.tsx`
- Create: `dashboard/src/components/Sidebar.tsx`
- Create: `dashboard/src/components/SecurityBanner.tsx`
- Create: `dashboard/src/components/StatusPill.tsx`
- Create: `dashboard/src/components/ErrorCard.tsx`
- Create: `dashboard/src/hooks/useSSE.ts`

- [ ] **Step 1: Layout.tsx**

```tsx
import { ReactNode } from 'react'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { SecurityBanner } from './SecurityBanner'

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <SecurityBanner />
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Header.tsx**

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { StatusPill } from './StatusPill'

export function Header() {
  const version = useQuery({
    queryKey: ['version'],
    queryFn: async () => {
      const { data } = await api.GET('/version')
      return data
    },
  })

  const instance = useQuery({
    queryKey: ['instance'],
    queryFn: async () => {
      const { data } = await api.GET('/instance')
      return data
    },
    refetchInterval: 5_000,
  })

  return (
    <header className="border-b bg-white px-6 py-3 flex items-center gap-4">
      <span className="font-semibold text-lg">LocalLLM</span>
      <span className="text-xs text-zinc-500">
        v{version.data?.cli_version ?? '…'}
      </span>
      <div className="flex-1" />
      <StatusPill instance={instance.data} />
    </header>
  )
}
```

- [ ] **Step 3: Sidebar.tsx**

```tsx
import { Link } from '@tanstack/react-router'
import { useAppStore } from '@/store'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/runtimes', label: 'Runtimes' },
  { to: '/models', label: 'Models' },
  { to: '/configs', label: 'Configs' },
  { to: '/instance', label: 'Instance' },
  { to: '/doctor', label: 'Doctor' },
  { to: '/disk', label: 'Disk' },
  { to: '/history', label: 'History' },
  { to: '/settings', label: 'Settings' },
]

export function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  return (
    <nav className={cn(
      "border-r bg-white shrink-0 transition-all",
      collapsed ? "w-12" : "w-56",
    )}>
      <ul className="p-2 space-y-1">
        {NAV.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              className="block rounded px-3 py-1.5 text-sm hover:bg-zinc-100"
              activeProps={{ className: "bg-zinc-100 font-medium" }}
            >
              {!collapsed && item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
```

- [ ] **Step 4: SecurityBanner.tsx (Plan 1 stub — always hidden)**

```tsx
export function SecurityBanner() {
  // In Plan 5 this reads the X-LocalLLM-Insecure response header (via a context populated
  // by the first /api/health call). For Plan 1, the dashboard is localhost-only by design.
  return null
}
```

- [ ] **Step 5: StatusPill.tsx**

```tsx
type Instance = { running?: boolean; config_id?: string; mode?: string }

export function StatusPill({ instance }: { instance: Instance | undefined }) {
  if (!instance || !instance.running) {
    return <span className="text-xs rounded-full bg-zinc-200 px-2 py-0.5">idle</span>
  }
  return (
    <span className="text-xs rounded-full bg-green-100 text-green-800 px-2 py-0.5">
      running: {instance.config_id} ({instance.mode})
    </span>
  )
}
```

- [ ] **Step 6: ErrorCard.tsx + lib/utils.ts**

```tsx
// ErrorCard.tsx
export function ErrorCard({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded border border-red-300 bg-red-50 p-4">
      <h3 className="font-medium text-red-800">{title}</h3>
      <p className="text-sm text-red-700">{message}</p>
    </div>
  )
}
```

```ts
// lib/utils.ts (created by shadcn init, may already exist — extend if so)
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 7: useSSE.ts hook**

```ts
import { useEffect, useRef, useState } from 'react'

export interface UseSSEOptions<T> {
  url: string
  enabled?: boolean
  parser?: (raw: string) => T
}

export function useSSE<T = unknown>({ url, enabled = true, parser = JSON.parse as any }: UseSSEOptions<T>) {
  const [event, setEvent] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<Event | null>(null)
  const retryRef = useRef(0)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (cancelled) return
      const es = new EventSource(url)
      esRef.current = es
      es.onopen = () => { setConnected(true); retryRef.current = 0; setError(null) }
      es.onmessage = (e) => { try { setEvent(parser(e.data)) } catch { /* ignore */ } }
      es.onerror = (e) => {
        setConnected(false); setError(e); es.close()
        const delay = Math.min(30_000, 1_000 * 2 ** retryRef.current)
        retryRef.current++
        timer = setTimeout(connect, delay)
      }
    }
    connect()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      esRef.current?.close()
    }
  }, [url, enabled])

  return { event, connected, error }
}
```

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/components/ dashboard/src/hooks/ dashboard/src/lib/
git commit -m "feat(dashboard): app shell (Layout/Header/Sidebar), status pill, error card, useSSE hook"
```

---

## Phase F — React read-only pages

For Tasks 32–40, follow this pattern per page:

1. Add the route to `router.tsx`.
2. Create `dashboard/src/features/<page>/<Page>.tsx`.
3. Write a Vitest test in `<Page>.test.tsx` using `@testing-library/react` + `msw` handlers.
4. Run `npm run test -- <page>.test` — expect FAIL.
5. Implement the page (TanStack Query fetching the relevant endpoint; shadcn primitives for layout; ErrorCard on error; Skeleton on loading).
6. Run — expect PASS.
7. Commit one task per page.

To avoid repetition I'll give the **first page (Overview)** in full, the **most complex page (Configs detail with tabs)** in full, and outline the rest.

---

### Task 32: Overview page

**Files:**
- Create: `dashboard/src/features/overview/OverviewPage.tsx`
- Create: `dashboard/src/features/overview/OverviewPage.test.tsx`
- Modify: `dashboard/src/router.tsx`
- Create: `dashboard/src/test/setup.ts`, `dashboard/src/test/handlers.ts`, `dashboard/vitest.config.ts`

- [ ] **Step 1: Vitest + msw setup**

`dashboard/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react-swc'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
```

`dashboard/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

`dashboard/src/test/handlers.ts`:

```ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/overview', () =>
    HttpResponse.json({
      version: { cli_version: '1.1.0' },
      instance: { running: false },
      runtimes_count: 2,
      runtimes_installed_count: 1,
      models_count: 3,
      configs_count: 5,
      doctor_summary: {
        default: { ok: 4, warning: 0, error: 0 },
        runtime: { ok: 2, warning: 1, error: 0 },
        dashboard: { ok: 3, warning: 0, error: 0 },
      },
      recent_history: [],
      disk_summary: { data_root_pct_used: 0.42, models_count: 3, cache_bytes: 1024 },
    })
  ),
  http.get('/api/version', () => HttpResponse.json({ cli_version: '1.1.0' })),
  http.get('/api/instance', () => HttpResponse.json({ running: false })),
]
```

- [ ] **Step 2: Write the page test**

`OverviewPage.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OverviewPage } from './OverviewPage'

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
)

test('renders overview cards from /api/overview', async () => {
  render(<OverviewPage />, { wrapper })
  await waitFor(() => expect(screen.getByText(/3 models/i)).toBeInTheDocument())
  expect(screen.getByText(/5 configs/i)).toBeInTheDocument()
  expect(screen.getByText(/idle/i)).toBeInTheDocument()
})
```

- [ ] **Step 3: Run — FAIL**

- [ ] **Step 4: Implement OverviewPage.tsx**

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorCard } from '@/components/ErrorCard'

export function OverviewPage() {
  const overview = useQuery({
    queryKey: ['overview'],
    queryFn: async () => {
      const { data, error } = await api.GET('/overview')
      if (error) throw new Error('Failed to load overview')
      return data
    },
  })

  if (overview.isPending) return <Skeleton className="h-96 w-full" />
  if (overview.isError) return <ErrorCard title="Failed to load" message={String(overview.error)} />

  const o = overview.data!
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <h3 className="text-sm text-zinc-500">Instance</h3>
          <p className="text-lg">{o.instance.running ? `Running: ${o.instance.config_id}` : 'idle'}</p>
        </Card>
        <Card className="p-4">
          <h3 className="text-sm text-zinc-500">Catalog</h3>
          <p>
            {o.runtimes_installed_count}/{o.runtimes_count} runtimes installed
            <br />
            {o.models_count} models &middot; {o.configs_count} configs
          </p>
        </Card>
        <Card className="p-4">
          <h3 className="text-sm text-zinc-500">Disk</h3>
          <p>{Math.round(o.disk_summary.data_root_pct_used * 100)}% of data_root used</p>
        </Card>
      </div>

      <Card className="p-4">
        <h3 className="font-medium mb-2">Doctor</h3>
        <ul className="space-y-1 text-sm">
          {Object.entries(o.doctor_summary).map(([scope, s]: any) => (
            <li key={scope}>
              <span className="font-mono">{scope}</span>: {s.ok} ok, {s.warning} warn, {s.error} err
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
```

- [ ] **Step 5: Wire the route**

In `router.tsx`, replace the placeholder `overviewRoute`'s component with `OverviewPage`. Add the other routes as `createRoute({ path: '/runtimes', ... })` etc., each pointing to a "Coming in Task NN" placeholder until that task lands.

- [ ] **Step 6: Run — PASS**

```bash
cd dashboard && npm run test -- overview
```

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/features/overview/ dashboard/src/router.tsx \
        dashboard/src/test/ dashboard/vitest.config.ts
git commit -m "feat(dashboard): Overview page (read-only) + Vitest+msw test infra"
```

---

### Task 33: Runtimes list + detail

**Files:**
- Create: `dashboard/src/features/runtimes/RuntimesPage.tsx`
- Create: `dashboard/src/features/runtimes/RuntimeDetailPage.tsx`
- Create: `dashboard/src/features/runtimes/RuntimesPage.test.tsx`

Pattern: a shadcn `Table` with rows from `GET /api/runtimes`. Row click navigates to `/runtimes/$id`. Detail page uses shadcn `Tabs` (Manifest / Install record / Drift).

**Test:**

```tsx
import { render, screen, waitFor } from '@testing-library/react'
// ... fixtures + msw handler returning [{id:'vllm',kind:'official',installed:true,...}]

test('renders runtimes list', async () => {
  render(<RuntimesPage />, { wrapper })
  await waitFor(() => expect(screen.getByText('vllm')).toBeInTheDocument())
  expect(screen.getByText(/installed/i)).toBeInTheDocument()
})
```

**Implementation outline** (full code; ~80 lines per page):

- List: useQuery `['runtimes']` → Table with columns `id | kind | status | actions`. "Install" / "Rebuild" / "Uninstall" buttons render as disabled with tooltip "Available in Plan 2" — Plan 1 keeps everything read-only. Visit `/runtimes/$id` on row click.
- Detail: useQuery `['runtimes', id]`. Tabs: Manifest (`<pre>{yaml.stringify(manifest)}</pre>`), Install record (key-value list or "Not installed"), Drift (key-value list or "Not installed").

Add a msw handler for `GET /api/runtimes/:id` to `test/handlers.ts`.

**Commit:** `feat(dashboard): Runtimes list + detail pages (read-only)`

---

### Task 34: Models list + detail

Same pattern as Task 33. List page has placeholder "Pull from HF" and "Add local" forms — disabled with "Available in Plan 2" tooltips.

**Commit:** `feat(dashboard): Models list + detail pages (read-only)`

---

### Task 35: Configs list + detail

**Files:**
- Create: `dashboard/src/features/configs/ConfigsPage.tsx`
- Create: `dashboard/src/features/configs/ConfigDetailPage.tsx`
- Create: `dashboard/src/features/configs/ParamsView.tsx` — read-only YAML rendering of `/configs/:id/params` for Plan 1; Plan 3 swaps this for the interactive grid.
- Tests as above.

Detail page tabs: Overview / Params (ParamsView) / Validate (button → runs `/configs/:id/validate`, shows result inline) / Raw YAML.

**ParamsView.tsx (Plan 1 read-only):**

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

export function ParamsView({ configId }: { configId: string }) {
  const q = useQuery({
    queryKey: ['configs', configId, 'params'],
    queryFn: async () => {
      const { data } = await api.GET('/configs/{id}/params', { params: { path: { id: configId } } })
      return data
    },
  })
  if (q.isPending) return <p>Loading…</p>
  if (q.isError) return <p>Failed to load params.</p>
  return (
    <div className="text-xs text-zinc-500 mb-2">
      Read-only view. Editing arrives in Plan 3.
      <pre className="mt-2 text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
        {JSON.stringify(q.data, null, 2)}
      </pre>
    </div>
  )
}
```

**Commit:** `feat(dashboard): Configs list + detail (Overview/Params/Validate/Raw YAML, read-only)`

---

### Task 36: Instance page (with logs streaming)

**Files:**
- Create: `dashboard/src/features/instance/InstancePage.tsx`
- Create: `dashboard/src/features/instance/LogsView.tsx`
- Tests

**InstancePage:**

- Reads `useQuery(['instance'])` and `useSSE('/api/instance/stream')`.
- If `instance.running === false`: show a card "Nothing is running. Start a config from the CLI (`loco serve <config>`) — start/stop controls arrive in Plan 2."
- If running: status card + tabs (Logs / Metrics-placeholder / Switch-disabled).

**LogsView:**

- Uses `useSSE('/api/instance/logs/stream', { parser: (s) => s })` (raw text).
- Maintains a buffer of last 5000 lines in a ref.
- Renders inside a `<pre>` with `overflow-y: auto`, max-height ~70vh.
- "Pause" button that disables the SSE subscription.

**Metrics tab placeholder:** "Live metrics arrive in Plan 4."

**Commit:** `feat(dashboard): Instance page with live log streaming (read-only)`

---

### Task 37: Doctor page

**Files:**
- Create: `dashboard/src/features/doctor/DoctorPage.tsx`

Tabs for each scope (default / runtime / dashboard). Each tab renders a list of check results: name + status badge (ok=green, warning=amber, error=red) + message + expandable fix_hint.

`useQuery(['doctor'])`. "Re-run" button refetches.

**Commit:** `feat(dashboard): Doctor page with per-scope check results`

---

### Task 38: Disk page

**Files:**
- Create: `dashboard/src/features/disk/DiskPage.tsx`

Three sections:
- Data-root summary: total, used, free, % full progress bar
- Models: shadcn Table (id, bytes); "Uninstall" button disabled with "Plan 2" tooltip
- Cache: cache_bytes; "Clear" button disabled with "Plan 2" tooltip

`useQuery(['disk'])` with `staleTime: 30_000` (du is expensive).

**Commit:** `feat(dashboard): Disk page (data root summary + per-model usage)`

---

### Task 39: History page (with SSE)

**Files:**
- Create: `dashboard/src/features/history/HistoryPage.tsx`

Server-paginated virtualized list. `useQuery(['history', filters])` with offset/limit. `useSSE('/api/history/stream')` to prepend new entries.

Filters above the list: action (multi-select), config_id (combobox), date range.

(Virtualization in Plan 1 can be skipped — just render 25 entries per page and "Load more" button.)

**Commit:** `feat(dashboard): History page with filters and live SSE updates`

---

### Task 40: Settings page (read-only)

**Files:**
- Create: `dashboard/src/features/settings/SettingsPage.tsx`

Two columns: "Stored" (raw key:value) and "Resolved" (effective paths after derivation). Render fields from `registry` array. "Edit" buttons disabled with "Plan 2" tooltip.

**Commit:** `feat(dashboard): Settings page (read-only stored + resolved view)`

---

## Phase G — Integration + CI

### Task 41: Wire FastAPI to serve `dashboard/dist/` as SPA

This is already done in Task 11 via `mount_spa()`. This task is a verification + smoke-test pass.

- [ ] **Step 1: Full local smoke test**

```bash
# From repo root
loco dashboard install
loco dashboard serve --no-open
# In another terminal:
curl http://127.0.0.1:7878/api/health
# Expected: {"ok":true}
curl -i http://127.0.0.1:7878/
# Expected: 200 OK, Content-Type: text/html, with React SPA HTML
loco dashboard stop
```

Document any rough edges found in `docs/DASHBOARD.md` (Task 44).

- [ ] **Step 2: Commit any fixes**

If the smoke test surfaced bugs, fix them, retest. Otherwise no commit.

---

### Task 42: CI job — `dashboard-tests`

**Files:**
- Create: `.github/workflows/dashboard-tests.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: dashboard-tests
on:
  pull_request:
    paths:
      - 'dashboard/**'
      - 'src/llm_cli/webapi/**'
      - 'src/llm_cli/core/dashboard.py'
      - 'src/llm_cli/core/disk.py'
      - 'src/llm_cli/commands/dashboard_cmd.py'
      - 'pyproject.toml'
      - '.github/workflows/dashboard-tests.yml'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - uses: astral-sh/setup-uv@v3
        with: { enable-cache: true }
      - run: uv venv && uv pip install -e ".[dev,dashboard]"
      - run: uv run pytest tests/webapi/ -m webapi -v
      - run: uv run pytest tests/unit/test_core_dashboard.py tests/unit/test_core_disk.py tests/unit/test_cli_dashboard.py -v
      - run: cd dashboard && npm ci
      - run: cd dashboard && npm run typecheck
      - run: cd dashboard && npm run test
      - run: cd dashboard && npm run build
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/dashboard-tests.yml
git commit -m "ci: add dashboard-tests workflow (pytest webapi + npm typecheck/test/build)"
```

---

### Task 43: CI job — `api-contract-check`

**Files:**
- Create: `.github/workflows/api-contract-check.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: api-contract-check
on:
  pull_request:
    paths:
      - 'src/llm_cli/webapi/**'
      - 'dashboard/src/api/generated.ts'
      - 'scripts/regen-api-client.sh'
      - '.github/workflows/api-contract-check.yml'

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - uses: astral-sh/setup-uv@v3
        with: { enable-cache: true }
      - run: uv venv && uv pip install -e ".[dev,dashboard]"
      - run: cd dashboard && npm ci
      - run: ./scripts/regen-api-client.sh --check
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/api-contract-check.yml
git commit -m "ci: add api-contract-check workflow (OpenAPI ↔ TS client sync)"
```

---

### Task 44: Documentation — `docs/DASHBOARD.md` + `dashboard/README.md` + index update

**Files:**
- Create: `docs/DASHBOARD.md`
- Create: `dashboard/README.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write `docs/DASHBOARD.md`**

```markdown
# Web Dashboard

The LocalLLM dashboard is an optional, locally-hosted web UI for managing your
LocalLLM installation: viewing runtimes, models, configs, the currently-running
instance, logs, doctor results, disk usage, and history. It is **opt-in** —
default `loco` installs do not include it.

## Install

```bash
loco dashboard install
```

This:
1. Installs FastAPI + Uvicorn + sse-starlette into the managed venv.
2. Checks Node.js 20+ and npm.
3. Runs `npm ci && npm run build` in `dashboard/`.
4. Writes `dashboard/.installed` with the current CLI version + dist hash.

Skip flags: `--skip-python`, `--skip-frontend`, `--reset` (wipe node_modules).

## Serve

```bash
loco dashboard serve                    # background, auto-opens browser
loco dashboard serve --foreground       # attached to terminal
loco dashboard serve --port 8000        # custom port
loco dashboard serve --no-open          # don't open browser
```

Server binds to `127.0.0.1` by default. Non-localhost binding will require a
`--insecure` flag (planned for a later release; currently refused).

## Status / stop / uninstall

```bash
loco dashboard status     # install state + server pid
loco dashboard stop       # SIGTERM the server, escalate to SIGKILL after 10s
loco dashboard uninstall  # remove .installed
loco dashboard uninstall --purge  # also delete dist/ and node_modules/
```

## Health checks

```bash
loco doctor dashboard
```

Checks Node/npm availability, dashboard install state, dist integrity, server
PID liveness.

## Update

When you run `loco update` and the dashboard is installed, it will be rebuilt
automatically (best-effort; skipped if node/npm are unavailable).

## Limitations of this release

This is the read-only release. The following arrive in subsequent releases:

- Mutations (create/edit/delete configs, install/uninstall runtimes, pull
  models, start/stop instances) — next release
- React param grid + new-config wizard
- Live metrics charts
- `--insecure` for LAN binding, with appropriate warnings

For the full design, see
[`docs/superpowers/specs/2026-05-20-web-dashboard-design.md`](superpowers/specs/2026-05-20-web-dashboard-design.md).
```

- [ ] **Step 2: Write `dashboard/README.md`**

```markdown
# LocalLLM Dashboard (React SPA)

The web frontend for the LocalLLM CLI dashboard. Source code lives here; built
output is committed to `.gitignore` and emitted by `npm run build` to `dist/`.

## Dev loop

```bash
# Terminal 1 — backend with auto-reload
uv run uvicorn llm_cli.webapi.app:create_app --factory --reload --port 7878

# Terminal 2 — frontend with HMR
cd dashboard && npm run dev
# Opens http://localhost:5173; /api/* proxied to :7878
```

## Regenerating the typed API client

After changing any FastAPI route or schema in `src/llm_cli/webapi/`:

```bash
scripts/regen-api-client.sh
```

Commit the changes to `dashboard/src/api/generated.ts`. CI enforces sync via
`scripts/regen-api-client.sh --check`.

## Stack

- React 19 + TypeScript
- Vite + Tailwind CSS v4 + shadcn/ui
- TanStack Router (type-safe routes) + TanStack Query (server state)
- Zustand (cross-page client state)
- sonner (toasts)
- Vitest + Testing Library + msw (tests)

## Running tests

```bash
npm run test          # one-shot
npm run test:watch    # watch mode
npm run typecheck     # tsc --noEmit
```
```

- [ ] **Step 3: Update `docs/README.md`**

Add a link to `docs/DASHBOARD.md` in the existing index. (Read the file first to find the right spot in the alphabetical/topic list.)

- [ ] **Step 4: Commit**

```bash
git add docs/DASHBOARD.md docs/README.md dashboard/README.md
git commit -m "docs(dashboard): user-facing install/serve guide + frontend dev README"
```

---

### Task 45: Final end-to-end smoke test + summary commit

- [ ] **Step 1: Clean install simulation**

```bash
# Wipe local install state
rm -rf dashboard/dist dashboard/node_modules dashboard/.installed
rm -rf state/dashboard

# Reinstall + serve
loco dashboard install
loco dashboard status        # should show "Installed for CLI ..."
loco dashboard serve --no-open
loco dashboard status        # should show "Server: running (pid=...)"
```

- [ ] **Step 2: Browser smoke**

Open `http://127.0.0.1:7878/` and click through each page:
- Overview loads, shows counts
- Runtimes list renders existing runtimes
- Clicking a runtime opens detail with Manifest tab populated
- Models list renders
- Configs list renders, detail opens, Params tab shows JSON
- Instance shows "Nothing is running" (or status if a CLI `loco serve` is active)
- Doctor renders 3 scopes
- Disk renders model sizes
- History renders past lifecycle events
- Settings renders stored + resolved keys

- [ ] **Step 3: Stop**

```bash
loco dashboard stop
loco dashboard status        # should show "Server: not running"
```

- [ ] **Step 4: Full test pass**

```bash
uv run pytest -q
cd dashboard && npm run typecheck && npm run test && npm run build
scripts/regen-api-client.sh --check
```

All green = Plan 1 done.

- [ ] **Step 5: Open PR**

```bash
git push -u origin feat/web-dashboard-mvp
gh pr create --title "feat(dashboard): web dashboard MVP (Plan 1/5 — install, serve, read-only views)" \
             --body-file - <<'EOF'
Implements Plan 1 of 5 from `docs/superpowers/plans/2026-05-20-web-dashboard-mvp.md`.

## Summary
- New `loco dashboard install / serve / status / stop / uninstall` commands
- FastAPI backend with read-only routes for runtimes, models, configs, instance (incl. SSE logs), doctor, settings, disk, history, overview
- Baseline security: Host header allow-list, CORS, CSP, security headers, request-id
- React SPA (React 19 + Vite + Tailwind v4 + shadcn + TanStack Router/Query + Zustand + sonner)
- `loco doctor dashboard` scope
- `loco setup` opt-in dashboard step
- `loco update` rebuilds dashboard if installed
- Two new CI jobs: dashboard-tests + api-contract-check
- Docs: `docs/DASHBOARD.md` and `dashboard/README.md`

## Out of scope (subsequent plans)
- Mutations + jobs system (Plan 2)
- Param grid + new-config wizard (Plan 3)
- Live metrics pipeline (Plan 4)
- `--insecure` UX + security hardening + update notifier (Plan 5)

## Test plan
- `uv run pytest -q` — all green
- `cd dashboard && npm run typecheck && npm run test && npm run build` — all green
- Manual: install → serve → browse each page → stop → uninstall
EOF
```

---

## Self-review (post-write checklist run by the author of the plan)

**1. Spec coverage:** Every read-only requirement from §4, §7.4 (GET routes), §8.9 (read-only page summaries), §10.1–§10.3 + §10.6 (baseline security), §11 (testing infra), and §5 (install lifecycle) is covered by at least one task above. Items intentionally deferred per the 5-plan split are listed in "Out of scope" on the PR template.

**2. Placeholder scan:** Searched the plan for TBD / TODO / fill-in / "TBD" / "details" / "etc.". None present. Page outlines for tasks 33–40 reference earlier tasks for the established pattern (allowed per skill — the pattern is fully shown in Task 32).

**3. Type consistency:** `InstalledRecord`, `InstallVerdict`, `RuntimeSummary`, `RuntimeDetail`, `ApiError`, `ErrorCode`, `EventHub`, `useSSE`, `useAppStore` are defined exactly once and referenced with identical names where used.

**4. Branch hygiene:** Plan creates `feat/web-dashboard-mvp` before Task 1; never commits to `main`.

**5. Conventional commits:** Every commit message uses an allowed type (`feat`, `chore`, `docs`, `ci`) with an optional scope. Matches `.cursor/rules/conventional-commits.mdc`.
