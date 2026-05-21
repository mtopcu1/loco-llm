"""Proxy chat completions to the running instance (avoids browser CORS)."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from llm_cli.core import lifecycle, registry
from llm_cli.core.settings import resolve_settings
from llm_cli.webapi.errors import ApiError, ErrorCode

router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    stream: bool = True
    max_tokens: int = Field(default=256, ge=1, le=8192)
    model: str | None = None


def _state_root():
    return lifecycle.state_root(resolve_settings())


def _require_running() -> lifecycle.LifecycleRecord:
    rec = lifecycle.read_running(_state_root())
    if rec is None:
        raise ApiError(
            ErrorCode.INSTANCE_NOT_RUNNING,
            "No instance is running",
            status_code=409,
        )
    return rec


def _upstream_base(rec: lifecycle.LifecycleRecord) -> str:
    host = "127.0.0.1"
    return f"http://{host}:{rec.port}"


def _config_runtime(config_id: str) -> tuple[dict[str, Any] | None, str | None]:
    cfg = registry.get_config_merged(config_id)
    if cfg is None:
        return None, None
    raw = cfg if isinstance(cfg, dict) else {}
    runtime = raw.get("runtime")
    return raw, str(runtime) if runtime else None


@router.get("/instance/chat/readiness", tags=["instance"])
async def chat_readiness(
    timeout_sec: float = Query(default=120.0, ge=5.0, le=600.0),
    interval_sec: float = Query(default=2.0, ge=0.5, le=10.0),
):
    rec = _require_running()
    base = _upstream_base(rec)
    url = f"{base}/v1/models"
    started = time.monotonic()
    last_error: str | None = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        while time.monotonic() - started < timeout_sec:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = _extract_model_ids(data)
                    cfg_raw, runtime_id = _config_runtime(rec.config_id)
                    latency_ms = int((time.monotonic() - started) * 1000)
                    return {
                        "ready": True,
                        "config_id": rec.config_id,
                        "port": rec.port,
                        "mode": rec.mode,
                        "runtime": runtime_id,
                        "models": models,
                        "latency_ms": latency_ms,
                        "config": cfg_raw,
                    }
                last_error = f"HTTP {resp.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            await asyncio.sleep(interval_sec)

    raise ApiError(
        ErrorCode.INTERNAL_ERROR,
        f"Model endpoint not ready within {timeout_sec:.0f}s"
        + (f" ({last_error})" if last_error else ""),
        details={"config_id": rec.config_id, "port": rec.port},
        status_code=504,
    )


def _extract_model_ids(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("data"), list):
        out: list[str] = []
        for item in data["data"]:
            if isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
        return out
    if data.get("id"):
        return [str(data["id"])]
    return []


@router.post("/instance/chat", tags=["instance"])
async def chat_completions(body: ChatRequest):
    rec = _require_running()
    base = _upstream_base(rec)
    url = f"{base}/v1/chat/completions"

    model = body.model
    if not model:
        model = await _default_model(base)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [m.model_dump() for m in body.messages],
        "stream": body.stream,
        "max_tokens": body.max_tokens,
    }

    timeout = httpx.Timeout(300.0, connect=30.0)

    if body.stream:
        return StreamingResponse(
            _stream_proxy(url, payload, timeout=timeout),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise ApiError(
                ErrorCode.INTERNAL_ERROR,
                f"Chat request failed: {exc}",
                status_code=502,
            ) from exc
        if resp.status_code >= 400:
            raise ApiError(
                ErrorCode.INTERNAL_ERROR,
                f"Upstream returned HTTP {resp.status_code}",
                details={"body": resp.text[:500]},
                status_code=502,
            )
        return JSONResponse(content=resp.json())


async def _default_model(base: str) -> str:
    url = f"{base}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                ids = _extract_model_ids(resp.json())
                if ids:
                    return ids[0]
    except httpx.HTTPError:
        pass
    return "default"


async def _stream_proxy(
    url: str, payload: dict[str, Any], *, timeout: httpx.Timeout
):
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code >= 400:
                    detail = await resp.aread()
                    msg = detail.decode("utf-8", errors="replace")[:500]
                    raise ApiError(
                        ErrorCode.INTERNAL_ERROR,
                        f"Upstream returned HTTP {resp.status_code}",
                        details={"body": msg},
                        status_code=502,
                    )
                async for chunk in resp.aiter_bytes():
                    yield chunk
    except ApiError:
        raise
    except httpx.HTTPError as exc:
        raise ApiError(
            ErrorCode.INTERNAL_ERROR,
            f"Chat stream failed: {exc}",
            status_code=502,
        ) from exc
