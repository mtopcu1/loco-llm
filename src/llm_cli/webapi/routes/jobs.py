from __future__ import annotations

import json

from fastapi import APIRouter
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
        raise ApiError(
            ErrorCode.JOB_NOT_FOUND,
            f"Job '{job_id}' not found",
            details={"job_id": job_id},
            status_code=404,
        )


async def iter_job_stream_events(job_id: str, sub):
    """Yield SSE event dicts for a job (snapshot, log tail, live updates)."""
    try:
        job = jobs_module.registry().get(job_id)
    except KeyError:
        return
    yield {
        "event": "snapshot",
        "data": json.dumps(job.as_dict(), sort_keys=True),
    }
    log_path = jobs_module.job_log_path(job_id)
    if job.status in ("queued", "running") and log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line:
                yield {
                    "event": "update",
                    "data": json.dumps({"log": line}, sort_keys=True),
                }
    if job.status in ("queued", "running"):
        async for ev in sub.events():
            yield {"event": "update", "data": json.dumps(ev, sort_keys=True)}


@router.get("/{job_id}/log")
def get_job_log(job_id: str):
    try:
        jobs_module.registry().get(job_id)
    except KeyError:
        raise ApiError(
            ErrorCode.JOB_NOT_FOUND,
            f"Job '{job_id}' not found",
            details={"job_id": job_id},
            status_code=404,
        )
    log_path = jobs_module.job_log_path(job_id)
    if not log_path.is_file():
        return {"lines": []}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return {"lines": text.splitlines()}


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    try:
        jobs_module.registry().get(job_id)
    except KeyError:
        raise ApiError(
            ErrorCode.JOB_NOT_FOUND,
            "no such job",
            details={"job_id": job_id},
            status_code=404,
        )
    sub = jobs_module.registry().subscribe(job_id)
    return EventSourceResponse(iter_job_stream_events(job_id, sub))


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    ok = jobs_module.registry().cancel(job_id)
    if not ok:
        raise ApiError(
            ErrorCode.JOB_NOT_CANCELABLE,
            "Job is not in a cancellable state",
            details={"job_id": job_id},
            status_code=409,
        )
    return {"cancelled": True}
