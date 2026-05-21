from __future__ import annotations

import asyncio
import json

import pytest

from llm_cli.core import jobs as jobs_module
from llm_cli.webapi.errors import ErrorCode


@pytest.fixture(autouse=True)
def reset_jobs():
    jobs_module._reset_for_tests()


@pytest.mark.webapi
def test_list_jobs_empty(test_client):
    r = test_client.get("/api/jobs", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.webapi
def test_get_job_log(test_client, monkeypatch, tmp_path):
    from datetime import UTC, datetime

    monkeypatch.setattr(jobs_module, "_jobs_dir", lambda: tmp_path)
    job_id = "log-job"
    (tmp_path / f"{job_id}.log").write_text("alpha\nbeta\n", encoding="utf-8")
    jobs_module.registry()._record(
        jobs_module.Job(
            id=job_id,
            kind="instance_start_wait",
            status="failed",
            created_at=datetime.now(tz=UTC),
            context={},
        )
    )
    jobs_module.registry()._order.insert(0, job_id)
    r = test_client.get(f"/api/jobs/{job_id}/log", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"lines": ["alpha", "beta"]}


@pytest.mark.webapi
def test_get_job_404(test_client):
    r = test_client.get("/api/jobs/no-such-id", headers={"Host": "testserver"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ErrorCode.JOB_NOT_FOUND.value


@pytest.mark.webapi
def test_cancel_job_not_cancelable(test_client):
    r = test_client.post("/api/jobs/no-such-id/cancel", headers={"Host": "testserver"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == ErrorCode.JOB_NOT_CANCELABLE.value


@pytest.mark.webapi
def test_list_and_get_job(test_client, webapi_repo, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs_module, "_jobs_dir", lambda: tmp_path)
    job_id = jobs_module.registry().start_subprocess(
        kind="update",
        context={"foo": "bar"},
        argv=["python", "-c", "pass"],
    )
    import time

    deadline = time.time() + 3.0
    while time.time() < deadline:
        if jobs_module.registry().get(job_id).status == "succeeded":
            break
        time.sleep(0.05)

    r = test_client.get("/api/jobs", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert any(j["id"] == job_id for j in r.json())

    r = test_client.get(f"/api/jobs/{job_id}", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == job_id
    assert body["status"] == "succeeded"
    assert body["context"] == {"foo": "bar"}


@pytest.mark.webapi
def test_cancel_running_subprocess_job(test_client, webapi_repo, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs_module, "_jobs_dir", lambda: tmp_path)
    job_id = jobs_module.registry().start_subprocess(
        kind="update",
        context={},
        argv=["python", "-c", "import time; time.sleep(0.5)"],
    )
    import time

    deadline = time.time() + 2.0
    while time.time() < deadline:
        if jobs_module.registry().get(job_id).status == "running":
            break
        time.sleep(0.05)

    r = test_client.post(f"/api/jobs/{job_id}/cancel", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"cancelled": True}

    deadline = time.time() + 5.0
    while time.time() < deadline:
        if jobs_module.registry().get(job_id).status == "cancelled":
            break
        time.sleep(0.05)
    assert jobs_module.registry().get(job_id).status == "cancelled"


@pytest.mark.asyncio
async def test_job_stream_events_include_json_log_tail(monkeypatch, tmp_path):
    from datetime import UTC, datetime

    from llm_cli.webapi.routes.jobs import iter_job_stream_events

    monkeypatch.setattr(jobs_module, "_jobs_dir", lambda: tmp_path)
    log_path = tmp_path / "abc123.log"
    log_path.write_text("line one\nline two\n", encoding="utf-8")
    job_id = "abc123"
    jobs_module.registry()._record(
        jobs_module.Job(
            id=job_id,
            kind="model_pull",
            status="running",
            created_at=datetime.now(tz=UTC),
            context={"url": "https://example.com/x.gguf"},
        )
    )
    jobs_module.registry()._order.insert(0, job_id)
    sub = jobs_module.registry().subscribe(job_id)

    collected: list[dict] = []

    async def collect():
        async for ev in iter_job_stream_events(job_id, sub):
            collected.append(ev)
            if len(collected) >= 3:
                break

    await asyncio.wait_for(collect(), timeout=2.0)

    events = collected
    assert events[0]["event"] == "snapshot"
    json.loads(events[0]["data"])
    log_events = [ev for ev in events if '"log"' in ev["data"]]
    assert len(log_events) >= 2
    assert json.loads(log_events[0]["data"]) == {"log": "line one"}
