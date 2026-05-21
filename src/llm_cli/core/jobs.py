"""In-memory job registry with persistent per-job log files.

Jobs survive HTTP request lifetime but die with the dashboard server.
That's Plan 2's contract; Plan 5+ may add persistent jobs.
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from llm_cli.core.lifecycle import state_dir, state_root
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.streams import EventHub

JobKind = Literal[
    "runtime_install",
    "runtime_rebuild",
    "runtime_uninstall",
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
    settings = resolve_settings()
    d = state_dir(state_root(settings)) / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_log_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.log"


def _subprocess_popen_kwargs() -> dict:
    """Isolate job children in a new process group so cancel can kill the full tree."""
    kw: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
    }
    if sys.platform != "win32":
        kw["start_new_session"] = True
    return kw


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        proc.terminate()
    deadline = time.time() + 10.0
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.1)
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            proc.kill()


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
        self._hub(job_id).publish(
            {"status": j.status, "progress": asdict(j.progress) if j.progress else None}
        )

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
        log_path = job_log_path(job_id)
        j = Job(
            id=job_id,
            kind=kind,
            status="queued",
            created_at=datetime.now(tz=UTC),
            context=dict(context),
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
                log.write(f"stage: {stage}\n")
                log.flush()
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
                log.write(f"error: {e}\n")
                log.flush()
            finally:
                self._publish_status(job_id)
                log.close()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(runner())
        except RuntimeError:
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
        log_path = job_log_path(job_id)
        j = Job(
            id=job_id,
            kind=kind,
            status="queued",
            created_at=datetime.now(tz=UTC),
            context=dict(context),
        )
        self._record(j)

        def runner() -> None:
            log_f = log_path.open("a", buffering=1, encoding="utf-8")
            try:
                full_env = os.environ.copy()
                full_env.setdefault("PYTHONUNBUFFERED", "1")
                if env:
                    full_env.update(env)
                proc = subprocess.Popen(
                    argv,
                    env=full_env,
                    cwd=str(cwd) if cwd else None,
                    **_subprocess_popen_kwargs(),
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
                        stage = line[len("[stage] ") :].rstrip()
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
                        j2.error = {
                            "code": "SUBPROCESS_FAILED",
                            "message": f"exit code {rc}",
                            "details": {"returncode": rc},
                        }
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
        if proc is not None:
            _terminate_process_tree(proc)
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
