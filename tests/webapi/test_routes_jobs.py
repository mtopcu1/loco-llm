from __future__ import annotations

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
        argv=["python", "-c", "import time; time.sleep(30)"],
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
