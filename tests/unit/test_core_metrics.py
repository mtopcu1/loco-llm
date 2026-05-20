from datetime import UTC, datetime, timedelta

import pytest

from llm_cli.core import metrics


def test_parse_prometheus_basic():
    text = """
# HELP vllm:tokens_per_second vLLM tokens per second
# TYPE vllm:tokens_per_second gauge
vllm:tokens_per_second{phase="decode"} 42.3
vllm:tokens_per_second{phase="prompt"} 1234.0
vllm:time_to_first_token_seconds 0.0875
"""
    fields = {
        "tps_decode": {"promql_metric": 'vllm:tokens_per_second{phase="decode"}'},
        "tps_prompt": {"promql_metric": 'vllm:tokens_per_second{phase="prompt"}'},
        "ttft_ms": {"promql_metric": "vllm:time_to_first_token_seconds", "multiplier": 1000},
        "missing": {"promql_metric": "does_not_exist"},
    }
    out = metrics.parse_prometheus(text, fields)
    assert out["tps_decode"] == 42.3
    assert out["tps_prompt"] == 1234.0
    assert out["ttft_ms"] == pytest.approx(87.5)
    assert out["missing"] is None


def test_append_and_read_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: tmp_path)
    metrics.append_snapshot("test-config", {"ts": "2026-05-20T07:30:05Z", "tps_decode": 42.3})
    snaps = list(metrics.read_snapshots("test-config"))
    assert len(snaps) == 1
    assert snaps[0]["tps_decode"] == 42.3


def test_aggregate_basic(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: tmp_path)
    now = datetime.now(tz=UTC)
    for i in range(100):
        ts = (now - timedelta(seconds=5 * (100 - i))).strftime("%Y-%m-%dT%H:%M:%SZ")
        metrics.append_snapshot("cfg", {"ts": ts, "tps_decode": float(i)})
    agg = metrics.aggregate("cfg", window="7d")
    assert agg["samples"] == 100
    assert agg["avg_tps_decode"] == pytest.approx(49.5)
    assert agg["p50_tps_decode"] == pytest.approx(49.5, abs=0.5)
    assert agg["p95_tps_decode"] >= 94.0


def test_sparkline_downsamples(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: tmp_path)
    now = datetime.now(tz=UTC)
    for i in range(60):
        ts = (now - timedelta(seconds=59 - i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        metrics.append_snapshot("cfg", {"ts": ts, "tps_decode": float(i)})
    spark = metrics.sparkline("cfg", bucket="10s", window="1m")
    assert 5 <= len(spark) <= 7
    for point in spark:
        assert "ts" in point and "tps_decode" in point


def test_aggregate_handles_error_snapshots(tmp_path, monkeypatch):
    """Snapshots with 'error' key are excluded from aggregation."""
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: tmp_path)
    metrics.append_snapshot("cfg", {"ts": "2026-05-20T07:30:00Z", "tps_decode": 50.0})
    metrics.append_snapshot("cfg", {"ts": "2026-05-20T07:30:05Z", "error": "timeout"})
    metrics.append_snapshot("cfg", {"ts": "2026-05-20T07:30:10Z", "tps_decode": 60.0})
    agg = metrics.aggregate("cfg", window="7d")
    assert agg["samples"] == 2
    assert agg["avg_tps_decode"] == pytest.approx(55.0)
