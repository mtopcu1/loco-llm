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


async def _instance_start_coro(
    config_id: str,
    mode: str,
    report,
) -> None:
    await report({"stage": "starting"})
    await asyncio.to_thread(lifecycle.serve_instance, config_id, mode=mode)
    await report({"stage": "ready"})


async def _instance_switch_coro(config_id: str, report) -> None:
    await report({"stage": "switching"})
    await asyncio.to_thread(lifecycle.switch_instance, config_id)
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
