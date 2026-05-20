from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from llm_cli.core import lifecycle
from llm_cli.core.settings import resolve_settings

router = APIRouter()


def _state_root() -> Path:
    return lifecycle.state_root(resolve_settings())


def _event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, sort_keys=True)}\n\n"


@router.get("/history", tags=["history"])
def get_history(
    limit: int = Query(default=25, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = None,
    config_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    items = lifecycle.read_history(_state_root())
    filtered: list[dict[str, Any]] = []
    for item in items:
        if action and str(item.get("action")) != action:
            continue
        if config_id and str(item.get("config_id") or item.get("id")) != config_id:
            continue
        ts = str(item.get("ts", ""))
        if since and ts < since:
            continue
        if until and ts > until:
            continue
        filtered.append(item)

    total = len(filtered)
    paged = filtered[offset : offset + limit]
    return {"items": paged, "total": total, "limit": limit, "offset": offset}


@router.get("/history/stream", tags=["history"])
async def stream_history(once: bool = Query(default=False)):
    async def _events() -> AsyncIterator[str]:
        root = _state_root()
        history_file = lifecycle.history_path(root)
        existing = lifecycle.read_history(root)
        for item in existing:
            yield _event(item)
        if once:
            return

        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.touch(exist_ok=True)
        with history_file.open("r", encoding="utf-8") as fh:
            fh.seek(0, 2)
            while True:
                line = fh.readline()
                if line:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        yield _event(payload)
                    continue
                await asyncio.sleep(0.25)

    return StreamingResponse(_events(), media_type="text/event-stream")
