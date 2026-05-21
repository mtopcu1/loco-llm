from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from llm_cli.core import jobs as jobs_module, versions
from llm_cli.webapi.job_runners import update_job

router = APIRouter(tags=["update"])

_CACHE: tuple[datetime, dict] | None = None


@router.get("/update/check")
def check_update():
    global _CACHE
    if _CACHE and datetime.now(tz=UTC) - _CACHE[0] < timedelta(minutes=5):
        return _CACHE[1]
    info = versions.check_for_update()
    body = {
        "current": info.current,
        "latest": info.latest,
        "update_available": info.update_available,
        "release_url": info.release_url,
    }
    _CACHE = (datetime.now(tz=UTC), body)
    return body


@router.post("/update")
def trigger_update(restart_dashboard: bool = Query(default=True)):
    async def factory(report):
        await update_job(restart=restart_dashboard, report=report)

    job_id = jobs_module.registry().start_async(
        kind="update",
        context={"restart_dashboard": restart_dashboard},
        coro_factory=factory,
    )
    return {"job_id": job_id}
