from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from llm_cli.core import jobs as jobs_module, lifecycle, registry
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


class StartInstanceBody(BaseModel):
    config_id: str
    mode: Literal["background", "systemd"] = "background"


class SwitchInstanceBody(BaseModel):
    config_id: str


def _state_root() -> Path:
    return lifecycle.state_root(resolve_settings())


def _snapshot() -> dict[str, Any]:
    rec = lifecycle.read_running(_state_root())
    if rec is None:
        return {"running": False}
    payload = asdict(rec)
    payload["running"] = True
    return payload


def _sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, sort_keys=True)}\n\n"


@router.get("/instance", tags=["instance"])
def get_instance():
    return _snapshot()


@router.get("/instance/stream", tags=["instance"])
async def stream_instance(once: bool = Query(default=False)):
    async def _events() -> AsyncIterator[str]:
        last_payload = _snapshot()
        yield _sse_data(last_payload)
        if once:
            return

        root = _state_root()
        running_file = lifecycle.running_path(root)
        last_mtime = running_file.stat().st_mtime if running_file.exists() else None
        heartbeat_ticks = 0

        while True:
            await asyncio.sleep(1.0)
            heartbeat_ticks += 1

            current_mtime = running_file.stat().st_mtime if running_file.exists() else None
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                last_payload = _snapshot()
                yield _sse_data(last_payload)
                continue

            if heartbeat_ticks >= 5:
                heartbeat_ticks = 0
                yield _sse_data(last_payload)

    return StreamingResponse(_events(), media_type="text/event-stream")


@router.get("/instance/metrics/stream", tags=["instance"])
async def instance_metrics_stream():
    from llm_cli.core import lifecycle_status, metrics, registry

    cur = lifecycle_status.current()
    if not cur.get("running"):
        raise ApiError(
            ErrorCode.INSTANCE_NOT_RUNNING,
            "Nothing running",
            status_code=409,
        )
    runtime_id = cur.get("runtime_id")
    rt = registry.get_runtime_merged(runtime_id) if runtime_id else None
    manifest_metrics = rt.manifest.get("metrics") if rt else None
    if not manifest_metrics:
        async def _no_metrics():
            yield {"event": "error", "data": json.dumps({"reason": "no_metrics"})}

        return EventSourceResponse(_no_metrics())

    hub = metrics.scheduler().hub_for(str(cur["config_id"]))
    sub = hub.subscribe()

    async def _gen():
        try:
            async for ev in sub.events():
                yield {"event": "snapshot", "data": json.dumps(ev, sort_keys=True)}
        finally:
            sub.close()

    return EventSourceResponse(_gen())


@router.get("/instance/logs/stream", tags=["instance"])
async def stream_instance_logs():
    async def _events() -> AsyncIterator[str]:
        root = _state_root()
        rec = lifecycle.read_running(root)
        if rec is None:
            yield _sse_data({"error": "INSTANCE_NOT_RUNNING"})
            return

        if rec.log_path:
            log_path = root / rec.log_path
        else:
            log_path = lifecycle.logs_dir(root) / f"{rec.config_id}.log"

        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)

        with log_path.open("r", encoding="utf-8") as fh:
            fh.seek(0, 2)
            while True:
                line = fh.readline()
                if line:
                    yield _sse_data({"line": line.rstrip("\r\n")})
                    continue
                await asyncio.sleep(0.25)

    return StreamingResponse(_events(), media_type="text/event-stream")


def _read_running_mode() -> str | None:
    root = _state_root()
    lifecycle.reconcile(root)
    rec = lifecycle.read_running(root)
    return rec.mode if rec is not None else None


def _serve_log_path(config_id: str) -> Path:
    return lifecycle.logs_dir(_state_root()) / f"{config_id}.log"


def _serve_log_tail_lines(config_id: str, *, max_lines: int = 60) -> list[str]:
    """Last lines from the config serve log (where readiness / runtime errors land)."""
    log_path = _serve_log_path(config_id)
    if not log_path.is_file():
        return [f"(no serve log file yet: {log_path})"]
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return ["(serve log file exists but is empty — failure may be before serve.sh wrote output)"]
    return lines[-max_lines:]


def _debug_hints(config_id: str) -> list[str]:
    log_path = _serve_log_path(config_id)
    return [
        f"serve log on disk: {log_path}",
        f"terminal: llm switch {config_id}",
        f"tail log: llm logs  (while any instance is running) or: Get-Content -Wait '{log_path}'",
        "check runtime installed: llm runtime list",
        "check model on disk: llm model list",
        "full diagnostics: llm doctor",
    ]


async def _report_instance_failure(config_id: str, report, exc: BaseException) -> None:
    await report({"stage": "failed"})
    msg = str(exc).strip()
    if msg:
        seen: set[str] = set()
        for line in msg.splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            await report({"log": f"error: {line}"})
    await report({"log": "--- serve log tail ---"})
    tail = _serve_log_tail_lines(config_id)
    for line in tail:
        await report({"log": line})
    if len(tail) <= 2 and tail and tail[0].startswith("("):
        await report({"log": "--- how to debug ---"})
        for hint in _debug_hints(config_id):
            await report({"log": hint})


async def _instance_start_coro(
    config_id: str,
    mode: str,
    report,
) -> None:
    await report({"stage": "starting", "log": f"config: {config_id} (mode={mode})"})
    try:
        await asyncio.to_thread(lifecycle.serve_instance, config_id, mode=mode)
    except Exception as exc:
        await _report_instance_failure(config_id, report, exc)
        raise
    await report({"stage": "ready"})


async def _instance_switch_coro(config_id: str, report) -> None:
    await report({"stage": "switching", "log": f"config: {config_id}"})
    try:
        await asyncio.to_thread(lifecycle.switch_instance, config_id)
    except Exception as exc:
        await _report_instance_failure(config_id, report, exc)
        raise
    await report({"stage": "ready"})


@router.post("/instance/start", tags=["instance"])
def start_instance(body: StartInstanceBody):
    if registry.get_config_merged(body.config_id) is None:
        raise ApiError(
            ErrorCode.CONFIG_NOT_FOUND,
            f"Config '{body.config_id}' not found",
            details={"config_id": body.config_id},
            status_code=404,
        )

    root = _state_root()
    lifecycle.reconcile(root)
    existing = lifecycle.read_running(root)
    if existing is not None:
        raise ApiError(
            ErrorCode.INSTANCE_ALREADY_RUNNING,
            f"Config '{existing.config_id}' is already running; stop it first or use switch",
            details={
                "config_id": existing.config_id,
                "requested_config_id": body.config_id,
            },
            status_code=409,
        )

    async def factory(report):
        await _instance_start_coro(body.config_id, body.mode, report)

    job_id = jobs_module.registry().start_async(
        kind="instance_start_wait",
        context={"config_id": body.config_id, "mode": body.mode},
        coro_factory=factory,
    )
    return {"job_id": job_id}


@router.post("/instance/stop", tags=["instance"])
def stop_instance_route():
    mode = _read_running_mode()
    if mode == "foreground":
        raise ApiError(
            ErrorCode.INSTANCE_FOREGROUND_NOT_STOPPABLE,
            "Foreground instance cannot be stopped via the dashboard; use Ctrl-C in the terminal",
            status_code=409,
        )
    lifecycle.stop_instance()
    return {"ok": True}


@router.post("/instance/switch", tags=["instance"])
def switch_instance_route(body: SwitchInstanceBody):
    mode = _read_running_mode()
    if mode == "foreground":
        raise ApiError(
            ErrorCode.INSTANCE_FOREGROUND_NOT_SWITCHABLE,
            "Foreground instance cannot be switched via the dashboard",
            status_code=409,
        )
    if registry.get_config_merged(body.config_id) is None:
        raise ApiError(
            ErrorCode.CONFIG_NOT_FOUND,
            f"Config '{body.config_id}' not found",
            details={"config_id": body.config_id},
            status_code=404,
        )

    async def factory(report):
        await _instance_switch_coro(body.config_id, report)

    job_id = jobs_module.registry().start_async(
        kind="instance_start_wait",
        context={"config_id": body.config_id, "action": "switch"},
        coro_factory=factory,
    )
    return {"job_id": job_id}
