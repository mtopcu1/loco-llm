from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from llm_cli.core import lifecycle
from llm_cli.core.settings import resolve_settings

router = APIRouter()


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
