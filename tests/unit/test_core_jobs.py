import asyncio
from pathlib import Path

import pytest

from llm_cli.core import jobs


@pytest.fixture(autouse=True)
def reset_registry():
    jobs._reset_for_tests()


@pytest.mark.asyncio
async def test_start_async_succeeds_and_records_status(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)

    async def work(report):
        await report({"stage": "starting"})
        await asyncio.sleep(0.01)
        await report({"stage": "done"})
        return "ok"

    job_id = jobs.registry().start_async(
        kind="runtime_install", context={"runtime_id": "x"}, coro_factory=work
    )
    await asyncio.sleep(0.1)
    j = jobs.registry().get(job_id)
    assert j.status == "succeeded"
    assert j.progress.stage == "done"
    log = (tmp_path / f"{job_id}.log").read_text()
    assert "stage: starting" in log


@pytest.mark.asyncio
async def test_start_async_failure_captures_error(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)

    async def work(report):
        raise RuntimeError("boom")

    job_id = jobs.registry().start_async(kind="model_pull", context={}, coro_factory=work)
    await asyncio.sleep(0.05)
    j = jobs.registry().get(job_id)
    assert j.status == "failed"
    assert "boom" in j.error["message"]


def test_start_subprocess_runs_to_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)
    job_id = jobs.registry().start_subprocess(
        kind="dashboard_install",
        context={},
        argv=["python", "-c", "print('[stage] hello'); print('done')"],
    )
    import time

    deadline = time.time() + 3.0
    while time.time() < deadline:
        j = jobs.registry().get(job_id)
        if j.status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.05)
    j = jobs.registry().get(job_id)
    assert j.status == "succeeded"
    log = (tmp_path / f"{job_id}.log").read_text()
    assert "[stage] hello" in log
    assert "done" in log


def test_list_returns_in_reverse_chronological(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)
    ids = []
    for _ in range(3):
        ids.append(
            jobs.registry().start_subprocess(
                kind="update", context={}, argv=["python", "-c", "pass"]
            )
        )
    listed = [j.id for j in jobs.registry().list()]
    assert listed[:3] == list(reversed(ids))


@pytest.mark.asyncio
async def test_subscribe_yields_status_change(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_jobs_dir", lambda: tmp_path)

    async def work(report):
        await asyncio.sleep(0.05)

    job_id = jobs.registry().start_async(
        kind="runtime_install", context={}, coro_factory=work
    )
    sub = jobs.registry().subscribe(job_id)

    events = []

    async def consume():
        async for ev in sub.events(timeout=1.0):
            events.append(ev)
            if any(e.get("status") == "succeeded" for e in events):
                break

    await asyncio.wait_for(consume(), timeout=2.0)
    assert any(e.get("status") == "succeeded" for e in events)
