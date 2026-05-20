from __future__ import annotations

from llm_cli.core import jobs as jobs_module
from llm_cli.webapi.errors import ApiError, ErrorCode
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter

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

    async def event_source():
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
        raise ApiError(
            ErrorCode.JOB_NOT_CANCELABLE,
            "Job is not in a cancellable state",
            details={"job_id": job_id},
            status_code=409,
        )
    return {"cancelled": True}
