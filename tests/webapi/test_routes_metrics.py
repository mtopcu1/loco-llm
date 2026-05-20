from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from llm_cli.core import metrics


@pytest.mark.webapi
def test_metrics_aggregate_empty(test_client, webapi_repo):
    del webapi_repo
    r = test_client.get(
        "/api/configs/cfg-1/metrics/aggregate?window=7d",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["samples"] == 0
    assert "total_uptime_seconds" in body


@pytest.mark.webapi
def test_metrics_aggregate_with_snapshots(test_client, webapi_repo, monkeypatch):
    metrics_dir = webapi_repo["repo_root"] / "state" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: metrics_dir)

    now = datetime.now(tz=UTC)
    for i in range(10):
        ts = (now - timedelta(seconds=5 * (10 - i))).strftime("%Y-%m-%dT%H:%M:%SZ")
        metrics.append_snapshot("cfg-1", {"ts": ts, "tps_decode": float(i)})

    r = test_client.get(
        "/api/configs/cfg-1/metrics/aggregate?window=7d",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["samples"] == 10
    assert body["avg_tps_decode"] == pytest.approx(4.5)


@pytest.mark.webapi
def test_metrics_sparkline(test_client, webapi_repo, monkeypatch):
    metrics_dir = webapi_repo["repo_root"] / "state" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: metrics_dir)

    now = datetime.now(tz=UTC)
    for i in range(20):
        ts = (now - timedelta(seconds=19 - i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        metrics.append_snapshot("cfg-2", {"ts": ts, "tps_decode": float(i)})

    r = test_client.get(
        "/api/configs/cfg-2/metrics/sparkline?bucket=10s&window=1m",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert "ts" in body[0]
