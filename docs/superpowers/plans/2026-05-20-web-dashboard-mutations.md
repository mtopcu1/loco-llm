# Web Dashboard Mutations & Jobs (Plan 2/5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add write operations to the dashboard MVP (Plan 1). Users can install/uninstall/rebuild runtimes, pull/add/uninstall models, create/edit/delete configs via a raw form (no param grid yet — that's Plan 3), start/stop/switch instances, and edit settings — all from the browser. Introduce the shared in-memory job registry (`core/jobs.py`) so long-running operations (install, pull, instance readiness) survive HTTP request lifetime and surface as a persistent Jobs tray in the sidebar.

**Architecture:** New `core/jobs.py` module owns the in-memory `Job` registry and per-job `state/jobs/<id>.log` files. POST/PUT/DELETE FastAPI routes either call into `core/*` synchronously (fast paths like delete-config, edit-settings) or enqueue a `Job` (long-running paths like runtime-install, model-pull). SSE streams per-job log lines + status changes. React grows: jobs tray drawer in the sidebar, mutation buttons across all the read-only pages, raw-YAML config editor, an instance start/stop/switch panel.

**Tech Stack:** Unchanged from Plan 1 — FastAPI, Uvicorn, sse-starlette on the backend; React 19, TanStack Query (now with `useMutation`), React Hook Form + Zod, sonner.

**Related spec:** `docs/superpowers/specs/2026-05-20-web-dashboard-design.md`

**Previous plan (must be merged first):** `docs/superpowers/plans/2026-05-20-web-dashboard-mvp.md`

**Subsequent plans:**
- Plan 3 — Param grid + new-config wizard (replaces the raw YAML editor introduced here)
- Plan 4 — Live metrics pipeline
- Plan 5 — Security hardening + update notifier + perf budgets + CI polish

**Implementation branch:** create `feat/web-dashboard-mutations` from `main` after Plan 1 merges.

---

## Background — what Plan 1 landed (and what this plan assumes)

- `webapi/` package with FastAPI factory, middleware (Host header, CORS, CSP, security headers, request-id), `webapi/errors.py` (`ApiError` + `ErrorCode` enum), `webapi/streams.py` (`EventHub`), `webapi/static.py` (SPA fallback).
- All GET-only routes for runtimes, models, configs (incl. read-only `/params` and `/validate`), instance (incl. SSE state + logs), doctor, settings, disk, history, overview, health, version.
- React shell + read-only pages for everything. Mutation buttons render as disabled with "Available in Plan 2" tooltips. Config detail's Params tab renders a read-only JSON dump.
- `loco dashboard install / serve / status / stop / uninstall` commands.
- `loco doctor dashboard` scope.
- `loco setup` opt-in dashboard step.
- `loco update` auto-rebuilds dashboard on version drift.
- `dashboard-tests` + `api-contract-check` CI jobs.

This plan **adds** mutations. It does **not** modify routes from Plan 1 except to register additional method handlers (`POST`/`PUT`/`DELETE`) on the same routers.

---

## Cross-plan invariants (must hold through Plan 5)

- **Every write goes through `llm_cli.core.*`.** If a route needs functionality only present in `commands/*`, extract it to `core/*` first as a sub-step. Same rule as Plan 1.
- **Jobs are the single mechanism for any operation that can exceed ~3 seconds.** Sync responses are for fast ops only.
- **ErrorCode is additive.** New error conditions get new enum values; never reuse a code for a different meaning.
- **TanStack Query keys** use the convention: `['noun']` for collections, `['noun', id]` for items, `['noun', id, 'subresource']` for sub-things. Mutations invalidate by exact key.
- **SSE topic names:** `instance`, `history`, `jobs/<id>`. (Plan 4 adds `metrics/<config-id>`.)
- **No raw file writes from `webapi/routes/`.** Always delegate to `core/*`.

---

## File map

**Create (Python):**
- `src/llm_cli/core/jobs.py` — `Job` dataclass, registry, `start_job()`, `cancel_job()`, per-job SSE hubs, log-file writer
- `src/llm_cli/webapi/routes/jobs.py` — `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/stream`, `POST /api/jobs/{id}/cancel`
- `tests/unit/test_core_jobs.py`
- `tests/webapi/test_routes_jobs.py`
- `tests/webapi/test_routes_runtimes_mutations.py`
- `tests/webapi/test_routes_models_mutations.py`
- `tests/webapi/test_routes_configs_mutations.py`
- `tests/webapi/test_routes_instance_mutations.py`
- `tests/webapi/test_routes_settings_mutations.py`

**Create (React):**
- `dashboard/src/features/jobs/JobsTray.tsx` — collapsible sidebar drawer
- `dashboard/src/features/jobs/JobsTrayItem.tsx` — single in-flight job row
- `dashboard/src/features/jobs/JobDetailSheet.tsx` — modal sheet with full SSE log
- `dashboard/src/features/configs/ConfigForm.tsx` — raw form (Plan 3 replaces with param grid)
- `dashboard/src/features/configs/NewConfigPage.tsx` — minimal new-config form (Plan 3 replaces with wizard)
- `dashboard/src/features/instance/InstanceControls.tsx` — start/stop/switch panel
- `dashboard/src/features/settings/SettingsForm.tsx` — editable form built from `KEY_REGISTRY`
- `dashboard/src/features/models/PullModelDialog.tsx`
- `dashboard/src/features/models/AddLocalModelDialog.tsx`
- `dashboard/src/hooks/useJobs.ts`, `useJob.ts`, `useStartJob.ts`
- `dashboard/src/lib/errorToToast.ts` — maps `ErrorCode` → friendly toast title

**Modify (Python):**
- `src/llm_cli/webapi/errors.py` — add new `ErrorCode` values (see Task 2)
- `src/llm_cli/webapi/app.py` — register `jobs.router`
- `src/llm_cli/webapi/routes/runtimes.py` — add POST install/rebuild, DELETE uninstall
- `src/llm_cli/webapi/routes/models.py` — add POST pull, POST add-local, DELETE
- `src/llm_cli/webapi/routes/configs.py` — add POST create, PUT update, DELETE
- `src/llm_cli/webapi/routes/instance.py` — add POST start, POST stop, POST switch
- `src/llm_cli/webapi/routes/settings.py` — add PUT settings/{key}
- `src/llm_cli/core/install_record.py` — extract `install_runtime()` from `commands/runtime_cmd.py` if not already there
- `src/llm_cli/core/model_registry.py` — extract `pull()` / `add_local()` / `uninstall()` from `commands/model_cmd.py`
- `src/llm_cli/core/registry.py` — extract `write_config()` / `delete_config()` from `commands/config_cmd.py`
- `src/llm_cli/core/lifecycle.py` — extract `serve()` / `stop()` / `switch()` from `commands/lifecycle_cmds.py`
- `src/llm_cli/core/settings.py` — already has `save_settings()`; just confirm a single-key `set()` helper exists (add if not)

**Modify (React):**
- `dashboard/src/components/Sidebar.tsx` — render `JobsTray` at the bottom
- `dashboard/src/features/runtimes/RuntimesPage.tsx` — enable install/rebuild/uninstall buttons
- `dashboard/src/features/runtimes/RuntimeDetailPage.tsx` — same
- `dashboard/src/features/models/ModelsPage.tsx` — enable Pull / Add-local; uninstall buttons
- `dashboard/src/features/configs/ConfigsPage.tsx` — enable New + Delete
- `dashboard/src/features/configs/ConfigDetailPage.tsx` — enable Edit (raw YAML) + Delete
- `dashboard/src/features/instance/InstancePage.tsx` — render `InstanceControls`
- `dashboard/src/features/settings/SettingsPage.tsx` — render `SettingsForm` instead of read-only view
- `dashboard/src/test/handlers.ts` — add msw handlers for new endpoints

**Untouched:**
- Param grid React component (Plan 3)
- Live metrics scrape + manifest extension (Plan 4)
- `--insecure` UX (Plan 5)
- Update notifier UI (Plan 5)

---

## Task 1: `core/jobs.py` — in-memory registry, per-job log file, SSE per job

**Files:**
- Create: `src/llm_cli/core/jobs.py`
- Create: `tests/unit/test_core_jobs.py`

`Job` matches the spec §15.5 shape:

```python
@dataclass
class Job:
    id: str                              # uuid4 hex
    kind: JobKind
    status: JobStatus                    # queued | running | succeeded | failed | cancelled
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    pid: int | None
    progress: JobProgress | None         # {percent: 0..100 | None, stage: str}
    error: dict | None                   # {code, message, details}
    context: dict                        # e.g. {"runtime_id": "vllm"} or {"config_id": "..."}
```

Public API:
- `registry()` → singleton `JobRegistry`
- `JobRegistry.start_async(kind, context, coro_factory)` — spawn an asyncio task; appends stdout via `JobLogWriter`; publishes status changes
- `JobRegistry.start_subprocess(kind, context, argv, env=None, cwd=None)` — spawn a subprocess; tee stdout+stderr into `state/jobs/<id>.log`; publish `progress.stage` lines parsed from stdout (any line starting with `[stage]` → progress event); on exit, set status `succeeded`/`failed` based on returncode
- `JobRegistry.cancel(id)` — SIGTERM → SIGKILL escalation (10s)
- `JobRegistry.get(id)`, `list()`
- `JobRegistry.subscribe(id)` — returns SSE hub subscription for that job's events (status + log lines)

- [ ] **Step 1: Write the failing tests**

```python
import asyncio
from pathlib import Path

import pytest

from llm_cli.core import jobs


@pytest.fixture(autouse=True)
def reset_registry():
    jobs._reset_for_tests()


@pytest.mark.asyncio
async def test_start_async_succeeds_and_records_status(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)

    async def work(report):
        await report({"stage": "starting"})
        await asyncio.sleep(0.01)
        await report({"stage": "done"})
        return "ok"

    job_id = jobs.registry().start_async(kind="runtime_install", context={"runtime_id": "x"}, coro_factory=work)
    await asyncio.sleep(0.1)
    j = jobs.registry().get(job_id)
    assert j.status == "succeeded"
    assert j.progress.stage == "done"
    log = (tmp_path / f"{job_id}.log").read_text()
    assert "stage: starting" in log


@pytest.mark.asyncio
async def test_start_async_failure_captures_error(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)

    async def work(report):
        raise RuntimeError("boom")

    job_id = jobs.registry().start_async(kind="model_pull", context={}, coro_factory=work)
    await asyncio.sleep(0.05)
    j = jobs.registry().get(job_id)
    assert j.status == "failed"
    assert "boom" in j.error["message"]


def test_start_subprocess_runs_to_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)
    job_id = jobs.registry().start_subprocess(
        kind="dashboard_install", context={},
        argv=["python", "-c", "print('[stage] hello'); print('done')"],
    )
    import time
    deadline = time.time() + 3.0
    while time.time() < deadline:
        j = jobs.registry().get(job_id)
        if j.status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.05)
    j = jobs.registry().get(job_id)
    assert j.status == "succeeded"
    log = (tmp_path / f"{job_id}.log").read_text()
    assert "[stage] hello" in log
    assert "done" in log


def test_list_returns_in_reverse_chronological(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)
    ids = []
    for _ in range(3):
        ids.append(jobs.registry().start_subprocess(
            kind="update", context={}, argv=["python", "-c", "pass"]))
    listed = [j.id for j in jobs.registry().list()]
    assert listed[:3] == list(reversed(ids))


@pytest.mark.asyncio
async def test_subscribe_yields_status_change(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)

    async def work(report):
        await asyncio.sleep(0.05)

    job_id = jobs.registry().start_async(kind="runtime_install", context={}, coro_factory=work)
    sub = jobs.registry().subscribe(job_id)

    events = []
    async def consume():
        async for ev in sub.events(timeout=1.0):
            events.append(ev)
            if any(e.get("status") == "succeeded" for e in events):
                break

    await asyncio.wait_for(consume(), timeout=2.0)
    assert any(e.get("status") == "succeeded" for e in events)
```

- [ ] **Step 2: Run — FAIL**

```bash
pytest tests/unit/test_core_jobs.py -v
```

- [ ] **Step 3: Implement `core/jobs.py`**

```python
"""In-memory job registry with persistent per-job log files.

Jobs survive HTTP request lifetime but die with the dashboard server.
That's Plan 2's contract; Plan 5+ may add persistent jobs.
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.streams import EventHub

JobKind = Literal[
    "runtime_install", "runtime_rebuild", "runtime_uninstall",
    "model_pull",
    "dashboard_install",
    "update",
    "instance_start_wait",
]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@dataclass
class JobProgress:
    percent: int | None
    stage: str


@dataclass
class Job:
    id: str
    kind: JobKind
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    pid: int | None = None
    progress: JobProgress | None = None
    error: dict | None = None
    context: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("created_at", "started_at", "finished_at"):
            v = d[k]
            d[k] = v.strftime("%Y-%m-%dT%H:%M:%SZ") if v is not None else None
        return d


def _jobs_dir() -> Path:
    p = resolve_settings().repo_root
    if p is None:
        raise RuntimeError("repo_root not configured")
    d = p / "state" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


class _JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []  # newest first
        self._hubs: dict[str, EventHub[dict]] = {}
        self._procs: dict[str, subprocess.Popen | None] = {}
        self._lock = threading.RLock()

    def list(self) -> list[Job]:
        with self._lock:
            return [self._jobs[i] for i in self._order]

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]

    def subscribe(self, job_id: str):
        return self._hub(job_id).subscribe()

    def _hub(self, job_id: str) -> EventHub[dict]:
        with self._lock:
            h = self._hubs.get(job_id)
            if h is None:
                h = EventHub[dict]()
                self._hubs[job_id] = h
            return h

    def _record(self, j: Job) -> None:
        with self._lock:
            self._jobs[j.id] = j
            if j.id not in self._order:
                self._order.insert(0, j.id)

    def _publish_status(self, job_id: str) -> None:
        j = self.get(job_id)
        self._hub(job_id).publish({"status": j.status, "progress": asdict(j.progress) if j.progress else None})

    def _publish_log_line(self, job_id: str, line: str) -> None:
        self._hub(job_id).publish({"log": line.rstrip()})

    def start_async(
        self,
        *,
        kind: JobKind,
        context: dict,
        coro_factory: Callable[[Callable[[dict], Awaitable[None]]], Awaitable[Any]],
    ) -> str:
        job_id = uuid.uuid4().hex
        log_path = _jobs_dir() / f"{job_id}.log"
        j = Job(
            id=job_id, kind=kind, status="queued",
            created_at=datetime.now(tz=UTC), context=dict(context),
        )
        self._record(j)

        async def runner() -> None:
            log = log_path.open("a", encoding="utf-8")

            async def report(progress: dict) -> None:
                stage = str(progress.get("stage", ""))
                percent = progress.get("percent")
                with self._lock:
                    self._jobs[job_id].progress = JobProgress(percent=percent, stage=stage)
                self._publish_status(job_id)
                log.write(f"stage: {stage}\n"); log.flush()
                self._publish_log_line(job_id, f"stage: {stage}")

            with self._lock:
                j2 = self._jobs[job_id]
                j2.status = "running"
                j2.started_at = datetime.now(tz=UTC)
            self._publish_status(job_id)

            try:
                await coro_factory(report)
                with self._lock:
                    j2 = self._jobs[job_id]
                    j2.status = "succeeded"
                    j2.finished_at = datetime.now(tz=UTC)
            except asyncio.CancelledError:
                with self._lock:
                    j2 = self._jobs[job_id]
                    j2.status = "cancelled"
                    j2.finished_at = datetime.now(tz=UTC)
                raise
            except Exception as e:
                with self._lock:
                    j2 = self._jobs[job_id]
                    j2.status = "failed"
                    j2.finished_at = datetime.now(tz=UTC)
                    j2.error = {"code": "INTERNAL_ERROR", "message": str(e), "details": {}}
                log.write(f"error: {e}\n"); log.flush()
            finally:
                self._publish_status(job_id)
                log.close()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(runner())
        except RuntimeError:
            # No running loop (test context): run in a thread with its own loop
            threading.Thread(target=lambda: asyncio.run(runner()), daemon=True).start()
        return job_id

    def start_subprocess(
        self,
        *,
        kind: JobKind,
        context: dict,
        argv: list[str],
        env: dict[str, str] | None = None,
        cwd: str | Path | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        log_path = _jobs_dir() / f"{job_id}.log"
        j = Job(
            id=job_id, kind=kind, status="queued",
            created_at=datetime.now(tz=UTC), context=dict(context),
        )
        self._record(j)

        def runner() -> None:
            log_f = log_path.open("a", buffering=1, encoding="utf-8")
            try:
                full_env = os.environ.copy()
                if env:
                    full_env.update(env)
                proc = subprocess.Popen(
                    argv,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=full_env, cwd=str(cwd) if cwd else None,
                )
                self._procs[job_id] = proc
                with self._lock:
                    j2 = self._jobs[job_id]
                    j2.status = "running"
                    j2.pid = proc.pid
                    j2.started_at = datetime.now(tz=UTC)
                self._publish_status(job_id)

                assert proc.stdout is not None
                for line in proc.stdout:
                    log_f.write(line)
                    self._publish_log_line(job_id, line)
                    if line.startswith("[stage] "):
                        stage = line[len("[stage] "):].rstrip()
                        with self._lock:
                            self._jobs[job_id].progress = JobProgress(percent=None, stage=stage)
                        self._publish_status(job_id)
                rc = proc.wait()
                with self._lock:
                    j2 = self._jobs[job_id]
                    j2.finished_at = datetime.now(tz=UTC)
                    if j2.status == "cancelled":
                        pass
                    elif rc == 0:
                        j2.status = "succeeded"
                    else:
                        j2.status = "failed"
                        j2.error = {"code": "SUBPROCESS_FAILED", "message": f"exit code {rc}", "details": {"returncode": rc}}
                self._publish_status(job_id)
            except Exception as e:
                with self._lock:
                    j2 = self._jobs[job_id]
                    j2.status = "failed"
                    j2.finished_at = datetime.now(tz=UTC)
                    j2.error = {"code": "INTERNAL_ERROR", "message": str(e), "details": {}}
                self._publish_status(job_id)
                log_f.write(f"error: {e}\n")
            finally:
                self._procs.pop(job_id, None)
                log_f.close()

        threading.Thread(target=runner, daemon=True).start()
        return job_id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            j = self._jobs.get(job_id)
            if j is None or j.status not in ("queued", "running"):
                return False
            j.status = "cancelled"
        proc = self._procs.get(job_id)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                return True
            deadline = time.time() + 10.0
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.1)
            if proc.poll() is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        self._publish_status(job_id)
        return True


_REGISTRY: _JobRegistry | None = None


def registry() -> _JobRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _JobRegistry()
    return _REGISTRY


def _reset_for_tests() -> None:
    global _REGISTRY
    _REGISTRY = _JobRegistry()
```

- [ ] **Step 4: Run — PASS**

```bash
pytest tests/unit/test_core_jobs.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/jobs.py tests/unit/test_core_jobs.py
git commit -m "feat(jobs): in-memory job registry with per-job log file and SSE fan-out"
```

---

## Task 2: Extend `ErrorCode` enum for mutation paths

**Files:**
- Modify: `src/llm_cli/webapi/errors.py`

Append to `ErrorCode`:

```python
# Mutation-specific
RUNTIME_ALREADY_INSTALLED = "RUNTIME_ALREADY_INSTALLED"
RUNTIME_IN_USE = "RUNTIME_IN_USE"             # in use by current running config
MODEL_ALREADY_REGISTERED = "MODEL_ALREADY_REGISTERED"
MODEL_PULL_INVALID_URL = "MODEL_PULL_INVALID_URL"
CONFIG_ALREADY_EXISTS = "CONFIG_ALREADY_EXISTS"
CONFIG_INVALID = "CONFIG_INVALID"
CONFIG_IN_USE = "CONFIG_IN_USE"               # delete refused; config is running
INSTANCE_FOREGROUND_NOT_SWITCHABLE = "INSTANCE_FOREGROUND_NOT_SWITCHABLE"
INSTANCE_FOREGROUND_NOT_STOPPABLE = "INSTANCE_FOREGROUND_NOT_STOPPABLE"
JOB_NOT_FOUND = "JOB_NOT_FOUND"
JOB_NOT_CANCELABLE = "JOB_NOT_CANCELABLE"
SETTINGS_VALIDATION_FAILED = "SETTINGS_VALIDATION_FAILED"
```

Commit: `git commit -m "feat(webapi): extend ErrorCode enum for mutation paths"`.

---

## Task 3: `webapi/routes/jobs.py` — list, detail, SSE stream, cancel

**Files:**
- Create: `src/llm_cli/webapi/routes/jobs.py`
- Create: `tests/webapi/test_routes_jobs.py`
- Modify: `src/llm_cli/webapi/app.py` (register router)

- [ ] **Step 1: Write the failing tests** (test list, detail 404, cancel) — pattern from Plan 1 Task 11.

- [ ] **Step 2: Implement**

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from llm_cli.core import jobs as jobs_module
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs():
    return [j.as_dict() for j in jobs_module.registry().list()]


@router.get("/{job_id}")
def get_job(job_id: str):
    try:
        return jobs_module.registry().get(job_id).as_dict()
    except KeyError:
        raise ApiError(ErrorCode.JOB_NOT_FOUND, f"Job '{job_id}' not found",
                       details={"job_id": job_id}, status_code=404)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    try:
        sub = jobs_module.registry().subscribe(job_id)
    except KeyError:
        raise ApiError(ErrorCode.JOB_NOT_FOUND, "no such job", details={"job_id": job_id}, status_code=404)

    async def event_source():
        # Emit the current state as the first event.
        try:
            yield {"event": "snapshot", "data": jobs_module.registry().get(job_id).as_dict()}
        except KeyError:
            return
        async for ev in sub.events():
            yield {"event": "update", "data": ev}

    return EventSourceResponse(event_source())


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    ok = jobs_module.registry().cancel(job_id)
    if not ok:
        raise ApiError(ErrorCode.JOB_NOT_CANCELABLE, "Job is not in a cancellable state",
                       details={"job_id": job_id}, status_code=409)
    return {"cancelled": True}
```

Register in `webapi/app.py`:

```python
from llm_cli.webapi.routes import jobs as jobs_routes
api.include_router(jobs_routes.router)
```

- [ ] **Step 3: Run — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(webapi): /api/jobs list/get/stream/cancel routes"
```

---

## Task 4: Runtime mutation routes (install / rebuild / uninstall)

**Files:**
- Modify: `src/llm_cli/webapi/routes/runtimes.py`
- Modify: `src/llm_cli/core/install_record.py` (extract `install_runtime()` if not already there)
- Create: `tests/webapi/test_routes_runtimes_mutations.py`

Endpoints:
- `POST /api/runtimes/{id}/install` → `{job_id}` (job runs `loco runtime install <id>`-equivalent via subprocess so we capture stdout to the job log; cleaner than re-implementing the install flow in-process)
- `POST /api/runtimes/{id}/rebuild` → `{job_id}` (calls `loco runtime rebuild <id>` subprocess; respects `?reset=true`)
- `DELETE /api/runtimes/{id}` → sync; calls `install_record.uninstall_runtime(id, purge=...)`. Refuses with `RUNTIME_IN_USE` if the runtime is currently serving anything.

- [ ] **Step 1: Tests** (one test per endpoint covering happy path + the in-use refusal for DELETE) — pattern from Plan 1.

- [ ] **Step 2: Implement** — example:

```python
@router.post("/runtimes/{runtime_id}/install")
def install_runtime(runtime_id: str):
    try:
        registry.get_runtime(runtime_id)
    except KeyError:
        raise ApiError(ErrorCode.RUNTIME_NOT_FOUND, "...", details={"runtime_id": runtime_id}, status_code=404)
    job_id = jobs_module.registry().start_subprocess(
        kind="runtime_install",
        context={"runtime_id": runtime_id},
        argv=["llm", "runtime", "install", runtime_id, "--yes"],
    )
    return {"job_id": job_id}


@router.delete("/runtimes/{runtime_id}")
def uninstall_runtime(runtime_id: str, purge: bool = False):
    running = lifecycle_status.current()
    if running and running.get("running") and running.get("runtime_id") == runtime_id:
        raise ApiError(ErrorCode.RUNTIME_IN_USE,
                       f"Runtime '{runtime_id}' is currently serving config '{running['config_id']}'.",
                       details={"runtime_id": runtime_id, "config_id": running["config_id"]},
                       status_code=409)
    install_record.uninstall_runtime(runtime_id, purge=purge)
    return {"ok": True}
```

- [ ] **Step 3: Run — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(webapi): POST /api/runtimes/{id}/install|rebuild + DELETE (sync uninstall)"
```

---

## Task 5: Model mutation routes (pull / add / uninstall)

**Files:**
- Modify: `src/llm_cli/webapi/routes/models.py`
- Modify: `src/llm_cli/core/model_registry.py` (extract `add_local()` / `uninstall()` if not already there)
- Create: `tests/webapi/test_routes_models_mutations.py`

Endpoints:
- `POST /api/models/pull` body `{url: str, id?: str, format?: str, include?: list, exclude?: list, force?: bool}` → `{job_id}`. Job subprocesses `loco model pull <url> [...flags]`.
- `POST /api/models/add` body `{id: str, path: str, format: str}` → sync; calls `model_registry.add_local(...)`.
- `DELETE /api/models/{id}?purge=true` → sync; calls `model_registry.uninstall(id, purge=purge)`.

- [ ] **Step 1: Tests** (pattern from Task 4).

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(webapi): POST /api/models/pull|add + DELETE (sync)"
```

---

## Task 6: Config mutation routes (create / update / delete)

**Files:**
- Modify: `src/llm_cli/webapi/routes/configs.py`
- Modify: `src/llm_cli/core/registry.py` (extract `write_config()`, `delete_config()`)
- Create: `tests/webapi/test_routes_configs_mutations.py`

Endpoints:
- `POST /api/configs` body = full config dict (`{id, runtime, model?, serve: {params: {...}}}`) → sync; calls `registry.write_config(...)`. 409 with `CONFIG_ALREADY_EXISTS` if id collides; 400 with `CONFIG_INVALID` if validation fails (include `errors: [...]`).
- `PUT /api/configs/{id}` — same shape, overwrites.
- `DELETE /api/configs/{id}` — sync; refuses with `CONFIG_IN_USE` if config is currently running.

Validation reuses the same `core/registry.validate_config_dict(...)` the CLI's `config new` uses — extract if needed.

- [ ] **Step 1: Tests** (happy path, conflict, validation failure, in-use deletion refusal).

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(webapi): POST/PUT/DELETE /api/configs with validation + in-use refusal"
```

---

## Task 7: Instance mutation routes (start / stop / switch)

**Files:**
- Modify: `src/llm_cli/webapi/routes/instance.py`
- Modify: `src/llm_cli/core/lifecycle.py` (ensure `serve()`, `stop()`, `switch()` are callable from `core/` not just `commands/`)
- Create: `tests/webapi/test_routes_instance_mutations.py`

Endpoints:
- `POST /api/instance/start` body `{config_id: str, mode: "background"|"systemd"}` → `{job_id}` for the readiness-wait phase. Foreground mode is not exposed via the API (no PTY in the browser; that's a Plan 5 candidate via xterm.js if we ever want it).
- `POST /api/instance/stop` → sync; refuses with `INSTANCE_FOREGROUND_NOT_STOPPABLE` if current instance is foreground (user must Ctrl-C their terminal).
- `POST /api/instance/switch` body `{config_id}` → `{job_id}` (readiness wait again); refuses with `INSTANCE_FOREGROUND_NOT_SWITCHABLE` if in foreground.

The job for start/switch runs `lifecycle.serve(config_id, mode=mode)` via `registry().start_async()` (not subprocess — we want in-process so the `state/running.json` write is observed by the same EventHub).

- [ ] **Step 1: Tests.**

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(webapi): POST /api/instance/start|stop|switch (async start, sync stop, fg-mode refusals)"
```

---

## Task 8: Settings mutation route

**Files:**
- Modify: `src/llm_cli/webapi/routes/settings.py`
- Modify: `src/llm_cli/core/settings.py` (ensure `set(key, value)` exists; add if not — should validate against `KEY_REGISTRY[key]["kind"]`)
- Create: `tests/webapi/test_routes_settings_mutations.py`

Endpoint:
- `PUT /api/settings/{key}` body `{value: str | null}` → sync; calls `settings.set(key, value)`. Returns the new resolved settings view. Null clears the override (where allowed by `KEY_REGISTRY`).

`SETTINGS_UNKNOWN_KEY` for unknown keys; `SETTINGS_VALIDATION_FAILED` for invalid values.

- [ ] **Step 1: Tests** (set valid, set invalid, set unknown, clear with null).

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(webapi): PUT /api/settings/{key} with validation against KEY_REGISTRY"
```

---

## Task 9: Regenerate the TypeScript API client

**Files:**
- Modify: `dashboard/src/api/generated.ts`

- [ ] **Step 1: Regenerate**

```bash
scripts/regen-api-client.sh
```

- [ ] **Step 2: Run CI-equivalent check locally**

```bash
scripts/regen-api-client.sh --check
```

Expected: "API client is up to date."

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/api/generated.ts
git commit -m "chore(dashboard): regen API client for Plan 2 mutation routes"
```

---

## Task 10: React `useJobs` / `useJob` / `useStartJob` hooks

**Files:**
- Create: `dashboard/src/hooks/useJobs.ts`
- Create: `dashboard/src/hooks/useJob.ts`
- Create: `dashboard/src/hooks/useStartJob.ts`

`useJobs()` — `useQuery(['jobs'])` returning the full job list; polled every 2s as a fallback when no specific job is being SSE'd.

`useJob(id)` — `useQuery(['jobs', id])` for the current snapshot, plus a `useSSE` subscription that calls `queryClient.setQueryData(['jobs', id], …)` on every event. Returns the merged live view.

`useStartJob()` — generic `useMutation` factory: caller passes the POST endpoint + body, mutation resolves to `{job_id}`, hook then opens the JobDetailSheet for that id.

```ts
// useJob.ts
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '@/api/client'
import { useSSE } from './useSSE'

export function useJob(id: string) {
  const qc = useQueryClient()
  const snapshot = useQuery({
    queryKey: ['jobs', id],
    queryFn: async () => (await api.GET('/jobs/{id}', { params: { path: { id } } })).data,
  })
  const sse = useSSE<{ status?: string; progress?: any; log?: string }>({
    url: `/api/jobs/${id}/stream`,
    enabled: !!snapshot.data,
  })
  useEffect(() => {
    if (!sse.event) return
    qc.setQueryData(['jobs', id], (prev: any) => prev ? { ...prev, ...sse.event } : prev)
    if (sse.event.status === 'succeeded' || sse.event.status === 'failed' || sse.event.status === 'cancelled') {
      qc.invalidateQueries({ queryKey: ['jobs'] })
    }
  }, [sse.event, qc, id])
  return snapshot
}
```

- [ ] **Step 1: Write a Vitest for `useJob`** — verifies SSE event merges into query data.

- [ ] **Step 2: Implement all three hooks.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): useJobs/useJob/useStartJob hooks with SSE-into-Query integration"
```

---

## Task 11: Jobs tray UI

**Files:**
- Create: `dashboard/src/features/jobs/JobsTray.tsx`
- Create: `dashboard/src/features/jobs/JobsTrayItem.tsx`
- Create: `dashboard/src/features/jobs/JobDetailSheet.tsx`
- Modify: `dashboard/src/components/Sidebar.tsx`

`JobsTray.tsx`: collapsible bottom drawer in the sidebar. Shows in-flight jobs (status ∈ {queued, running}) sorted by `started_at`. Each row: kind icon, context summary (`runtime: vllm` etc.), stage, elapsed, cancel button. Clicking a row opens `JobDetailSheet`.

`JobDetailSheet.tsx`: shadcn `Sheet` that renders job metadata + a streaming log viewer (read-only, monospace, max-height 60vh, auto-scroll-on-new). Driven by `useJob(id)`.

`Sidebar.tsx`: render `<JobsTray />` at the bottom (sticky to bottom).

- [ ] **Step 1: Tests** — render with mocked `useJobs` returning two running jobs; assert both visible; click cancel triggers the mutation.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): Jobs tray in sidebar + JobDetailSheet with streaming log"
```

---

## Task 12: Wire mutation buttons into Runtimes page

**Files:**
- Modify: `dashboard/src/features/runtimes/RuntimesPage.tsx`
- Modify: `dashboard/src/features/runtimes/RuntimeDetailPage.tsx`

Replace the "Available in Plan 2" disabled buttons with real mutations:

- "Install" / "Rebuild" → `useStartJob()` against the corresponding POST endpoint; on success: toast success + open JobDetailSheet.
- "Uninstall" → confirm dialog → `useMutation` against DELETE; on success: toast + invalidate `['runtimes']` + close detail page.

Error handling: `lib/errorToToast.ts` maps `RUNTIME_IN_USE` → "Cannot uninstall: this runtime is currently serving a config. Stop the instance first."

- [ ] **Step 1: Tests** — happy path mutation + 409 error path.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): enable runtime install/rebuild/uninstall mutations with error toasts"
```

---

## Task 13: Wire mutation buttons into Models page

**Files:**
- Modify: `dashboard/src/features/models/ModelsPage.tsx`
- Create: `dashboard/src/features/models/PullModelDialog.tsx`
- Create: `dashboard/src/features/models/AddLocalModelDialog.tsx`

`PullModelDialog`: React Hook Form + Zod over `{url, id?, format?, include?, exclude?, force?}`. Submit → `useStartJob` against `POST /api/models/pull` → open JobDetailSheet.

`AddLocalModelDialog`: form over `{id, path, format}`. Submit → `useMutation` against `POST /api/models/add` → toast + invalidate.

Uninstall: confirm dialog with `purge` toggle.

- [ ] **Step 1: Tests** — render dialog, submit invalid form (validation fires), submit valid form (mutation called).

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): enable model pull/add/uninstall with form validation"
```

---

## Task 14: Raw config form + create/edit/delete

**Files:**
- Create: `dashboard/src/features/configs/ConfigForm.tsx`
- Create: `dashboard/src/features/configs/NewConfigPage.tsx`
- Modify: `dashboard/src/features/configs/ConfigsPage.tsx`
- Modify: `dashboard/src/features/configs/ConfigDetailPage.tsx`
- Modify: `dashboard/src/router.tsx` (add `/configs/new`)

`ConfigForm`: React Hook Form over `{id, runtime, model?, serve: {params: {...}}}` where `serve.params` is a JSON textarea for v1. Validation: Zod schema mirrors backend.

`NewConfigPage`: a thin wrapper that mounts `ConfigForm` in "create" mode.

ConfigDetailPage's Raw YAML tab gains an "Edit" toggle → mounts `ConfigForm` in "update" mode pre-populated with the current config.

`ConfigsPage`: "New" button → `/configs/new`; "Delete" per-row with confirm.

(The proper React param grid replaces this raw editor in Plan 3.)

- [ ] **Step 1: Tests** — create flow happy path, update flow happy path, delete with in-use refusal.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): raw config form for create/edit + delete (param grid arrives in Plan 3)"
```

---

## Task 15: Instance controls (start / stop / switch)

**Files:**
- Create: `dashboard/src/features/instance/InstanceControls.tsx`
- Modify: `dashboard/src/features/instance/InstancePage.tsx`

`InstanceControls`:
- When idle: combobox of all configs + mode radio (`background` | `systemd`) + Start button → `useStartJob` against `POST /api/instance/start` → JobDetailSheet for readiness.
- When running: shows current status + Stop button + Switch combobox + Switch button.
- When running in foreground: shows Stop button disabled with tooltip "Started in foreground from terminal — use Ctrl-C in that terminal to stop."

InstancePage swaps the "controls arrive in Plan 2" placeholder for `<InstanceControls />`.

- [ ] **Step 1: Tests** — idle state shows start, running state shows stop+switch, foreground shows disabled stop.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): instance start/stop/switch controls"
```

---

## Task 16: Settings form

**Files:**
- Create: `dashboard/src/features/settings/SettingsForm.tsx`
- Modify: `dashboard/src/features/settings/SettingsPage.tsx`

`SettingsForm`: one row per key from `registry`. Type-aware input (`path` → text + folder picker icon (no native picker in v1 — just text)). "Save" per row → `useMutation` against `PUT /api/settings/{key}`. "Reset to default" → `useMutation` with null body (where the key supports clearing).

- [ ] **Step 1: Tests** — edit data_root → mutation called with correct payload; validation error displayed as a row-level error.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): editable Settings form built from KEY_REGISTRY"
```

---

## Task 17: Error-to-toast mapping

**Files:**
- Create: `dashboard/src/lib/errorToToast.ts`

Maps `ErrorCode` enum string → user-friendly toast title + body. Default fallback uses the server message verbatim. Wire into `useStartJob` and every `useMutation` `onError` across the dashboard.

```ts
import { toast } from 'sonner'

const TITLES: Record<string, string> = {
  RUNTIME_IN_USE: "Runtime in use",
  CONFIG_IN_USE: "Config is currently running",
  CONFIG_INVALID: "Configuration invalid",
  // ...etc, one per ErrorCode
}

export function errorToToast(err: unknown) {
  const body = (err as any)?.error
  if (body && body.code) {
    toast.error(TITLES[body.code] ?? body.code, {
      description: body.message,
      action: body.fix_hint ? { label: 'Fix', onClick: () => {/* TODO Plan 5: implement fix hints */} } : undefined,
    })
    return
  }
  toast.error("Request failed", { description: String(err) })
}
```

(`fix_hint` is captured but acting on it is deferred to Plan 5; for now we just surface the message.)

- [ ] **Step 1: Test** — calling `errorToToast` with a known code produces the mapped title.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): centralized error→toast mapping by ErrorCode"
```

---

## Task 18: End-to-end smoke + PR

- [ ] **Step 1: Full local smoke test**

```bash
# Backend
loco dashboard install
loco dashboard serve --no-open

# In another terminal:
curl -X POST http://127.0.0.1:7878/api/runtimes/stub-runtime/install \
     -H 'Host: 127.0.0.1:7878' -H 'Content-Type: application/json'
# Expected: 200, {"job_id": "..."}

curl http://127.0.0.1:7878/api/jobs -H 'Host: 127.0.0.1:7878'
# Expected: list including the install job.
```

In the browser:
- Install a runtime via Runtimes page → watch progress in Jobs tray → confirm success
- Create a new config via Configs page → save → see it in the list
- Start that config from Instance page → see status update → watch logs → stop
- Edit a setting via Settings page → verify it persists

- [ ] **Step 2: All tests green**

```bash
uv run pytest -q
cd dashboard && npm run typecheck && npm run test && npm run build
scripts/regen-api-client.sh --check
```

- [ ] **Step 3: PR**

```bash
git push -u origin feat/web-dashboard-mutations
gh pr create --title "feat(dashboard): mutations + jobs system (Plan 2/5)" --body "..."
```

---

## Self-review

1. **Spec coverage:** every mutation in spec §7.4 is implemented; jobs from §7.6 + §15.5 are implemented as `core/jobs.py`; jobs tray + mutation UIs from §8.9 are wired.
2. **Placeholder scan:** no TBD/TODO/fill-in.
3. **Type consistency:** `Job` / `JobStatus` / `JobKind` / `JobProgress` defined once in `core/jobs.py`, consumed unchanged in `webapi/routes/jobs.py` and `dashboard/src/api/generated.ts`. `ErrorCode` additions are namespace-clean (no reuse). React hook names (`useJobs`, `useJob`, `useStartJob`) and Query keys (`['jobs']`, `['jobs', id]`) consistent.
4. **Branch hygiene:** `feat/web-dashboard-mutations` from `main` after Plan 1 merges.
5. **Conventional commits:** every commit message uses an allowed type.
