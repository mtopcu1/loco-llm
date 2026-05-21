# Web Dashboard Live Metrics (Plan 4/5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the live-metrics pipeline. When a config is serving, the dashboard polls the runtime's Prometheus `/metrics` endpoint every 5 seconds, appends snapshots to `state/metrics/<config-id>.jsonl`, fans out to a per-config SSE hub, and renders live TPS / TTFT / P50 / P95 cards and sparklines on the Instance page. Aggregated stats (`avg_*`, `p50_*`, `p95_*`, `total_uptime_seconds`) feed the Config detail page's Overview tab.

**Architecture:** New `core/metrics.py` module owns scrape tasks, JSONL snapshot writing, and pure-Python aggregation. Runtime manifests gain an optional `metrics:` block (per the spec §9.1). The dashboard's FastAPI app starts/stops one `MetricsScrapeTask` per running config in response to lifecycle events. Two new REST endpoints surface the data; one new SSE endpoint pushes live snapshots. React grows a Metrics tab on the Instance page and metrics cards on the Config detail Overview tab.

**Tech Stack:** Adds `prometheus-client` to the `[dashboard]` extras (~150 KB pure-Python, the canonical Prometheus parser). No new frontend deps — sparklines are SVG `<path>` elements computed client-side.

**Related spec:** `docs/superpowers/specs/2026-05-20-web-dashboard-design.md` (§9 Live metrics pipeline, §8.9 Instance page Metrics tab)

**Previous plans (must be merged first):** Plans 1, 2, 3.

**Subsequent plans:**
- Plan 5 — Security hardening + update notifier + perf budgets + CI polish

**Implementation branch:** `feat/web-dashboard-metrics` from `main` after Plan 3 merges.

---

## Background — what Plans 1+2+3 landed

- Plan 1: read-only routes, instance SSE state/logs streams, `state/jobs/` infra. Runtime manifests have no `metrics:` block yet.
- Plan 2: jobs system (`core/jobs.py`), instance start/stop/switch via lifecycle module. Crucially, lifecycle changes are surfaced via an in-process publisher (or polling `state/running.json` in the bare minimum from Plan 1 Task 22).
- Plan 3: param grid + wizard — no overlap with metrics.

This plan **adds** a new `MetricsScrapeTask` lifecycle wired to the existing lifecycle events. Nothing about `state/running.json`, `state/logs/`, or the existing instance SSE changes.

---

## Cross-plan invariants (additions)

- **`metrics:` manifest block is optional.** Missing or `null` → no live metrics for that runtime; UI shows the "no live metrics" state. Adding the block to a runtime is purely additive.
- **`state/metrics/<config-id>.jsonl` is append-only.** No rotation in v1; that's a Plan 5+ concern.
- **One scrape task per running config.** Dashboard restart re-initializes from `state/running.json`; existing JSONL is preserved.
- **5s scrape interval is fixed in v1.** Configurable in v2.
- **Aggregation is pure Python.** No numpy / pandas / time-series DB.

---

## File map

**Create (Python):**
- `src/llm_cli/core/metrics.py` — `MetricsScrapeTask`, `aggregate()`, `sparkline()`, `parse_prometheus()`, manifest helpers
- `src/llm_cli/webapi/routes/metrics.py` — `GET /api/configs/{id}/metrics/aggregate`, `GET /api/configs/{id}/metrics/sparkline`
- `tests/unit/test_core_metrics.py`
- `tests/webapi/test_routes_metrics.py`
- `tests/integration/test_metrics_scrape_lifecycle.py` (uses a stub HTTP server returning Prometheus text)

**Create (React):**
- `dashboard/src/features/metrics/MetricsCards.tsx` — large-number live values
- `dashboard/src/features/metrics/Sparkline.tsx` — SVG-based 60-point sparkline
- `dashboard/src/features/metrics/MetricsTab.tsx` — composes both, driven by SSE + aggregate query
- `dashboard/src/features/metrics/__tests__/Sparkline.test.tsx`
- `dashboard/src/features/metrics/__tests__/MetricsCards.test.tsx`
- `dashboard/src/hooks/useMetricsStream.ts`

**Modify (Python):**
- `pyproject.toml` — add `prometheus-client>=0.20,<1.0` to `[dashboard]` extras
- `src/llm_cli/webapi/app.py` — startup hook: subscribe `core/metrics.py` task scheduler to lifecycle events; shutdown hook: cancel all scrape tasks
- `src/llm_cli/webapi/routes/instance.py` — add `GET /api/instance/metrics/stream` SSE
- `src/llm_cli/core/lifecycle.py` — ensure lifecycle state changes publish to an in-process `EventHub[dict]` (extract from Plan 1's polling-based stream into a proper publisher; the polling fallback may stay as a backup)
- `runtimes/vllm/manifest.yaml` — add the `metrics:` block (full schema in Task 2)
- `runtimes/llamacpp/manifest.yaml` — add the `metrics:` block
- `runtimes/stub-runtime/manifest.yaml` — explicitly set `metrics: null` (so the "no live metrics" path is obviously tested)
- `src/llm_cli/webapi/routes/runtimes.py` — `RuntimeSummary.has_metrics` becomes `True` when the manifest's `metrics` block is present + non-null (Plan 1 always returned `False`)

**Modify (React):**
- `dashboard/src/features/instance/InstancePage.tsx` — replace the "Live metrics arrive in Plan 4" placeholder with `<MetricsTab />`
- `dashboard/src/features/configs/ConfigDetailPage.tsx` — Overview tab gains a metrics summary card (uses the aggregate endpoint)
- `dashboard/src/features/overview/OverviewPage.tsx` — if something is running, the "running now" card shows live TPS+TTFT mini-numbers
- `dashboard/src/test/handlers.ts` — handlers for new endpoints

**Modify (docs):**
- `docs/add-a-runtime.md` — document the new optional `metrics:` block

**Untouched:**
- Jobs system (no metrics-related jobs in v1)
- Security model (Plan 5)
- TUI (no live metrics surface)

---

## Task 1: Add `prometheus-client` dep

**Files:**
- Modify: `pyproject.toml`

In `[project.optional-dependencies]`, extend `dashboard`:

```toml
dashboard = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.30,<1.0",
    "sse-starlette>=2.1,<3.0",
    "prometheus-client>=0.20,<1.0",
]
```

Then:

```bash
uv pip install -e ".[dev,dashboard]"
python -c "import prometheus_client; print(prometheus_client.__version__)"
```

Commit: `chore(deps): add prometheus-client to dashboard extras`.

---

## Task 2: Runtime manifest extension — `metrics:` block

**Files:**
- Modify: `runtimes/vllm/manifest.yaml`
- Modify: `runtimes/llamacpp/manifest.yaml`
- Modify: `runtimes/stub-runtime/manifest.yaml`
- Modify: `docs/add-a-runtime.md`

Append to `runtimes/vllm/manifest.yaml`:

```yaml
metrics:
  endpoint: /metrics
  format: prometheus
  fields:
    tps_decode:
      promql_metric: vllm:tokens_per_second{phase="decode"}
      label: "Decode TPS"
      unit: "tok/s"
    tps_prompt:
      promql_metric: vllm:tokens_per_second{phase="prompt"}
      label: "Prompt TPS"
      unit: "tok/s"
    ttft_ms:
      promql_metric: vllm:time_to_first_token_seconds
      multiplier: 1000
      label: "TTFT"
      unit: "ms"
    requests_in_flight:
      promql_metric: vllm:num_requests_running
      label: "In-flight"
      unit: "req"
```

(Metric names above are illustrative; verify against the vLLM version pinned by the runtime's build script. Adjust before committing.)

For `runtimes/llamacpp/manifest.yaml`:

```yaml
metrics:
  endpoint: /metrics
  format: prometheus
  fields:
    tps_decode:
      promql_metric: llamacpp:tokens_per_second_per_request
      label: "Decode TPS"
      unit: "tok/s"
    ttft_ms:
      promql_metric: llamacpp:time_to_first_token_seconds
      multiplier: 1000
      label: "TTFT"
      unit: "ms"
    kv_cache_pct:
      promql_metric: llamacpp:kv_cache_usage_ratio
      multiplier: 100
      label: "KV cache"
      unit: "%"
```

(Verify against actual llama.cpp server output — if `llama-server` doesn't expose `/metrics`, document that here and set `metrics: null`; aggregation still works from history but live UI shows the "not available" state.)

For `runtimes/stub-runtime/manifest.yaml`:

```yaml
metrics: null
```

Append to `docs/add-a-runtime.md` a "Metrics" section explaining the schema, its optionality, and how to find the right promql metric names.

Commit: `feat(runtime-manifest): add optional metrics block (vllm, llamacpp populated; stub null)`.

---

## Task 3: `core/metrics.py` — parse, append, aggregate, sparkline

**Files:**
- Create: `src/llm_cli/core/metrics.py`
- Create: `tests/unit/test_core_metrics.py`

Functions:
- `parse_prometheus(text: str, fields: dict) -> dict[str, float | None]` — given the raw `/metrics` text and the manifest's `fields` map, return resolved values keyed by field id. Missing or unparseable → `None`.
- `append_snapshot(config_id: str, snapshot: dict) -> None` — writes one JSONL line to `state/metrics/<config-id>.jsonl`.
- `read_snapshots(config_id: str, *, since: datetime | None = None, until: datetime | None = None) -> Iterator[dict]` — lazy reader.
- `aggregate(config_id: str, *, window: str = "7d") -> dict` — returns `{samples, avg_<field>, p50_<field>, p95_<field>, total_uptime_seconds}`.
- `sparkline(config_id: str, *, bucket: str = "5m", window: str = "24h") -> list[dict]` — downsampled `[{ts, <field>: mean}]`.

`window` and `bucket` accept the suffixes `s`, `m`, `h`, `d`.

- [ ] **Step 1: Write the failing tests**

```python
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
    base = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    for i in range(60):
        ts = (base + timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        metrics.append_snapshot("cfg", {"ts": ts, "tps_decode": float(i)})
    spark = metrics.sparkline("cfg", bucket="10s", window="1m")
    # 60 samples / 10s buckets = ~6 buckets
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
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `core/metrics.py`**

```python
"""Live metrics scrape, JSONL persistence, and pure-Python aggregation."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from prometheus_client.parser import text_string_to_metric_families

from llm_cli.core.settings import resolve_settings


def _metrics_dir() -> Path:
    repo = resolve_settings().repo_root
    if repo is None:
        raise RuntimeError("repo_root not configured")
    d = repo / "state" / "metrics"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapshot_path(config_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", config_id)
    return _metrics_dir() / f"{safe}.jsonl"


def _parse_window(s: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([smhd])", s.strip())
    if not m:
        raise ValueError(f"Bad window/bucket: {s!r}")
    n = int(m.group(1))
    return {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
            "h": timedelta(hours=n), "d": timedelta(days=n)}[m.group(2)]


def _parse_label_filter(query: str) -> tuple[str, dict[str, str]]:
    """`vllm:foo{phase="decode",model="a"}` → ("vllm:foo", {phase: decode, model: a})"""
    if "{" not in query:
        return query, {}
    name, rest = query.split("{", 1)
    rest = rest.rstrip("}")
    labels = {}
    if rest:
        for chunk in re.split(r",(?=\w+=)", rest):
            k, _, v = chunk.partition("=")
            labels[k.strip()] = v.strip().strip('"')
    return name.strip(), labels


def parse_prometheus(text: str, fields: dict[str, dict]) -> dict[str, float | None]:
    """Resolve manifest `fields` against the prometheus text response."""
    by_name: dict[str, list[tuple[dict[str, str], float]]] = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            by_name.setdefault(sample.name, []).append((dict(sample.labels), sample.value))

    out: dict[str, float | None] = {}
    for field_id, spec in fields.items():
        promql = str(spec["promql_metric"])
        multiplier = float(spec.get("multiplier", 1))
        name, label_filter = _parse_label_filter(promql)
        matches = by_name.get(name, [])
        for labels, value in matches:
            if all(labels.get(k) == v for k, v in label_filter.items()):
                out[field_id] = value * multiplier
                break
        else:
            out[field_id] = None
    return out


def append_snapshot(config_id: str, snapshot: dict) -> None:
    p = _snapshot_path(config_id)
    line = json.dumps(snapshot, separators=(",", ":"))
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_snapshots(
    config_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Iterator[dict]:
    p = _snapshot_path(config_id)
    if not p.is_file():
        return iter(())
    def gen():
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since is not None or until is not None:
                    try:
                        ts = datetime.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                    except (KeyError, ValueError):
                        continue
                    if since and ts < since:
                        continue
                    if until and ts >= until:
                        continue
                yield rec
    return gen()


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def aggregate(config_id: str, *, window: str = "7d") -> dict:
    since = datetime.now(tz=UTC) - _parse_window(window)
    snaps = [s for s in read_snapshots(config_id, since=since) if "error" not in s]
    out: dict = {"samples": len(snaps), "total_uptime_seconds": _total_uptime(config_id, since)}
    if not snaps:
        return out
    field_keys = {k for s in snaps for k in s if k != "ts"}
    for f in field_keys:
        values = sorted(float(s[f]) for s in snaps if isinstance(s.get(f), (int, float)))
        if not values:
            continue
        out[f"avg_{f}"] = sum(values) / len(values)
        out[f"p50_{f}"] = _percentile(values, 0.50)
        out[f"p95_{f}"] = _percentile(values, 0.95)
    return out


def _total_uptime(config_id: str, since: datetime) -> int:
    """Sum start→stop intervals from history.jsonl for this config."""
    from llm_cli.core.lifecycle import read_history
    try:
        events = read_history()
    except Exception:
        return 0
    total = 0
    running_since: datetime | None = None
    for ev in events:
        if ev.get("config_id") != config_id:
            continue
        ts = _parse_ts(ev.get("ts"))
        if ts is None or ts < since:
            continue
        if ev.get("action") == "start" and running_since is None:
            running_since = ts
        elif ev.get("action") == "stop" and running_since is not None:
            total += int((ts - running_since).total_seconds())
            running_since = None
    if running_since is not None:
        total += int((datetime.now(tz=UTC) - running_since).total_seconds())
    return total


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def sparkline(
    config_id: str, *, bucket: str = "5m", window: str = "24h"
) -> list[dict]:
    since = datetime.now(tz=UTC) - _parse_window(window)
    bucket_td = _parse_window(bucket)
    snaps = [s for s in read_snapshots(config_id, since=since) if "error" not in s]
    if not snaps:
        return []
    field_keys = {k for s in snaps for k in s if k != "ts" and isinstance(s.get(k), (int, float))}
    buckets: dict[int, dict[str, list[float]]] = {}
    bucket_seconds = int(bucket_td.total_seconds())
    for s in snaps:
        ts = _parse_ts(s.get("ts"))
        if ts is None:
            continue
        idx = int(ts.timestamp() // bucket_seconds)
        buckets.setdefault(idx, {f: [] for f in field_keys})
        for f in field_keys:
            v = s.get(f)
            if isinstance(v, (int, float)):
                buckets[idx][f].append(float(v))
    out: list[dict] = []
    for idx in sorted(buckets):
        ts = datetime.fromtimestamp(idx * bucket_seconds, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        point = {"ts": ts}
        for f, vals in buckets[idx].items():
            point[f] = sum(vals) / len(vals) if vals else None
        out.append(point)
    return out
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(metrics): prometheus parsing, JSONL persistence, percentile aggregation, sparkline"
```

---

## Task 4: `MetricsScrapeTask` — lifecycle-aware scrape loop

**Files:**
- Modify: `src/llm_cli/core/metrics.py` (append `MetricsScrapeTask` class + scheduler)
- Modify: `src/llm_cli/webapi/app.py` (startup/shutdown hooks)
- Create: `tests/integration/test_metrics_scrape_lifecycle.py`

`MetricsScrapeTask`:
- Constructor: `(config_id, runtime_id, manifest, host, port, hub)` — manifest's `metrics` block, the runtime's bind host:port, an `EventHub[dict]` for live fan-out.
- `start()` → spawns an asyncio task that:
  - Polls every 5s.
  - On success: parses, appends snapshot, publishes to hub.
  - On failure: appends error snapshot, increments error counter; after 3 consecutive errors, suspends for 60s.
  - On cancellation: closes cleanly.

`MetricsScheduler` (singleton, started by `webapi/app.py` startup hook):
- Subscribes to the lifecycle event bus.
- On `instance_started(config_id, runtime_id, host, port)`: if the runtime's manifest has `metrics:` populated, instantiate + start a `MetricsScrapeTask`.
- On `instance_stopped(config_id)`: cancel the corresponding task.
- On dashboard startup: read `state/running.json`; if running, start the task.
- On dashboard shutdown: cancel all tasks.

- [ ] **Step 1: Integration test using a stub HTTP server**

```python
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from llm_cli.core import metrics
from llm_cli.webapi.streams import EventHub


PROM_BODY = """# TYPE vllm:tokens_per_second gauge
vllm:tokens_per_second{phase="decode"} 99.0
"""


class StubHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(PROM_BODY.encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *args): pass


@pytest.fixture
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), StubHandler)
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    yield ("127.0.0.1", port)
    server.shutdown()


@pytest.mark.asyncio
async def test_scrape_task_writes_snapshot_and_publishes(stub_server, tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: tmp_path)
    host, port = stub_server
    manifest_metrics = {
        "endpoint": "/metrics",
        "fields": {
            "tps_decode": {"promql_metric": 'vllm:tokens_per_second{phase="decode"}'},
        },
    }
    hub = EventHub()
    task = metrics.MetricsScrapeTask(
        config_id="cfg", runtime_id="vllm", manifest_metrics=manifest_metrics,
        host=host, port=port, hub=hub, interval_seconds=0.1,
    )
    task.start()

    sub = hub.subscribe()
    received = []
    async def consume():
        async for ev in sub.events(timeout=2.0):
            received.append(ev)
            if len(received) >= 2:
                break
    await asyncio.wait_for(consume(), timeout=3.0)
    await task.stop()

    assert len(received) >= 2
    assert received[0]["tps_decode"] == 99.0
    snaps = list(metrics.read_snapshots("cfg"))
    assert len(snaps) >= 2
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `MetricsScrapeTask` + `MetricsScheduler` in `core/metrics.py`**

```python
import asyncio
import logging

import httpx

logger = logging.getLogger("llm_cli.core.metrics")


class MetricsScrapeTask:
    def __init__(
        self, *, config_id: str, runtime_id: str, manifest_metrics: dict,
        host: str, port: int, hub, interval_seconds: float = 5.0,
    ) -> None:
        self.config_id = config_id
        self.runtime_id = runtime_id
        self.manifest_metrics = manifest_metrics
        self.host = host
        self.port = port
        self.hub = hub
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._consec_errors = 0

    def start(self) -> None:
        if self._task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run())
        except RuntimeError:
            import threading
            threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True).start()

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _run(self) -> None:
        url = f"http://{self.host}:{self.port}{self.manifest_metrics['endpoint']}"
        async with httpx.AsyncClient(timeout=2.0) as client:
            while True:
                try:
                    r = await client.get(url, headers={"Host": f"{self.host}:{self.port}"})
                    if r.status_code >= 400:
                        snap = {"ts": _now_iso(), "error": f"http_{r.status_code}"}
                        append_snapshot(self.config_id, snap)
                        self.hub.publish(snap)
                        self._consec_errors += 1
                    else:
                        parsed = parse_prometheus(r.text, self.manifest_metrics["fields"])
                        snap = {"ts": _now_iso(), **parsed}
                        append_snapshot(self.config_id, snap)
                        self.hub.publish(snap)
                        self._consec_errors = 0
                except httpx.TimeoutException:
                    snap = {"ts": _now_iso(), "error": "timeout"}
                    append_snapshot(self.config_id, snap)
                    self.hub.publish(snap)
                    self._consec_errors += 1
                except Exception as e:
                    logger.warning("metrics parse error for %s: %s", self.config_id, e)
                    snap = {"ts": _now_iso(), "error": "parse"}
                    append_snapshot(self.config_id, snap)
                    self.hub.publish(snap)

                if self._consec_errors >= 3:
                    await asyncio.sleep(60.0)
                    self._consec_errors = 0
                else:
                    await asyncio.sleep(self.interval_seconds)


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Scheduler -------------------------------------------------------------

class MetricsScheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, MetricsScrapeTask] = {}
        self._hubs: dict[str, "EventHub[dict]"] = {}

    def hub_for(self, config_id: str):
        from llm_cli.webapi.streams import EventHub
        h = self._hubs.get(config_id)
        if h is None:
            h = EventHub[dict]()
            self._hubs[config_id] = h
        return h

    async def on_instance_started(self, config_id: str, runtime_id: str, host: str, port: int) -> None:
        from llm_cli.core import registry
        try:
            rt = registry.get_runtime(runtime_id)
        except KeyError:
            return
        manifest_metrics = rt.manifest_dict().get("metrics")
        if not manifest_metrics:
            return
        if config_id in self._tasks:
            await self._tasks[config_id].stop()
        task = MetricsScrapeTask(
            config_id=config_id, runtime_id=runtime_id,
            manifest_metrics=manifest_metrics, host=host, port=port,
            hub=self.hub_for(config_id),
        )
        task.start()
        self._tasks[config_id] = task

    async def on_instance_stopped(self, config_id: str) -> None:
        task = self._tasks.pop(config_id, None)
        if task:
            await task.stop()

    async def stop_all(self) -> None:
        for task in list(self._tasks.values()):
            await task.stop()
        self._tasks.clear()


_SCHEDULER: MetricsScheduler | None = None


def scheduler() -> MetricsScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = MetricsScheduler()
    return _SCHEDULER
```

- [ ] **Step 4: Wire startup/shutdown hooks in `webapi/app.py`**

```python
@app.on_event("startup")
async def _startup_metrics():
    from llm_cli.core import metrics, lifecycle_status
    cur = lifecycle_status.current()
    if cur and cur.get("running"):
        await metrics.scheduler().on_instance_started(
            config_id=cur["config_id"], runtime_id=cur["runtime_id"],
            host="127.0.0.1", port=cur.get("port", 8000),
        )
    # Subscribe to lifecycle event bus (extracted in core/lifecycle.py)
    from llm_cli.core.lifecycle import event_bus
    async def _on_event(ev):
        if ev.get("action") == "start":
            await metrics.scheduler().on_instance_started(
                config_id=ev["config_id"], runtime_id=ev["runtime_id"],
                host="127.0.0.1", port=ev.get("port", 8000),
            )
        elif ev.get("action") == "stop":
            await metrics.scheduler().on_instance_stopped(ev["config_id"])
    event_bus().subscribe_async(_on_event)


@app.on_event("shutdown")
async def _shutdown_metrics():
    from llm_cli.core import metrics
    await metrics.scheduler().stop_all()
```

(If `core/lifecycle.event_bus()` doesn't exist yet — Plan 1's instance SSE may have used a polling fallback — add it now. The bus should publish on every `serve()`, `stop()`, `switch()` call.)

- [ ] **Step 5: Run integration test — PASS**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(metrics): MetricsScrapeTask + scheduler wired to lifecycle events"
```

---

## Task 5: REST routes — aggregate + sparkline

**Files:**
- Create: `src/llm_cli/webapi/routes/metrics.py`
- Modify: `src/llm_cli/webapi/app.py`
- Create: `tests/webapi/test_routes_metrics.py`

Endpoints:
- `GET /api/configs/{id}/metrics/aggregate?window=7d` → `aggregate()` result
- `GET /api/configs/{id}/metrics/sparkline?bucket=5m&window=24h` → `sparkline()` result

```python
from fastapi import APIRouter, Query

from llm_cli.core import metrics

router = APIRouter(tags=["metrics"])


@router.get("/configs/{config_id}/metrics/aggregate")
def metrics_aggregate(config_id: str, window: str = Query("7d")):
    return metrics.aggregate(config_id, window=window)


@router.get("/configs/{config_id}/metrics/sparkline")
def metrics_sparkline(
    config_id: str,
    bucket: str = Query("5m"),
    window: str = Query("24h"),
):
    return metrics.sparkline(config_id, bucket=bucket, window=window)
```

- [ ] **Step 1: Tests + impl + commit.**

```bash
git commit -m "feat(webapi): GET /api/configs/{id}/metrics/aggregate + sparkline"
```

---

## Task 6: SSE — `/api/instance/metrics/stream`

**Files:**
- Modify: `src/llm_cli/webapi/routes/instance.py`

Endpoint streams the per-config metrics hub for the currently-running config. If nothing is running or the running config's runtime has no metrics, the stream emits one `{"event":"error","data":{"reason":"no_metrics"}}` and closes.

```python
from sse_starlette.sse import EventSourceResponse


@router.get("/instance/metrics/stream")
async def instance_metrics_stream():
    from llm_cli.core import metrics, lifecycle_status
    cur = lifecycle_status.current()
    if not (cur and cur.get("running")):
        return JSONResponse(status_code=409,
                            content={"error": {"code": "INSTANCE_NOT_RUNNING", "message": "Nothing running"}})
    hub = metrics.scheduler().hub_for(cur["config_id"])
    sub = hub.subscribe()
    async def gen():
        async for ev in sub.events():
            yield {"event": "snapshot", "data": ev}
    return EventSourceResponse(gen())
```

- [ ] **Step 1: Test** — start a scrape task by hand, subscribe, assert at least one snapshot is received.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(webapi): GET /api/instance/metrics/stream SSE"
```

---

## Task 7: Regen API client

```bash
scripts/regen-api-client.sh
git add dashboard/src/api/generated.ts
git commit -m "chore(dashboard): regen API client for metrics endpoints"
```

---

## Task 8: React — `useMetricsStream` hook + `<MetricsCards>`

**Files:**
- Create: `dashboard/src/hooks/useMetricsStream.ts`
- Create: `dashboard/src/features/metrics/MetricsCards.tsx`

`useMetricsStream`: wraps `useSSE('/api/instance/metrics/stream')`, returns the latest snapshot + a ring buffer of the last 60 snapshots.

```ts
import { useEffect, useRef, useState } from 'react'
import { useSSE } from './useSSE'

export interface Snapshot { ts: string; [field: string]: number | string | null | undefined }

export function useMetricsStream() {
  const sse = useSSE<Snapshot>({ url: '/api/instance/metrics/stream' })
  const bufferRef = useRef<Snapshot[]>([])
  const [, force] = useState(0)
  useEffect(() => {
    if (!sse.event) return
    bufferRef.current = [...bufferRef.current.slice(-59), sse.event]
    force((n) => n + 1)
  }, [sse.event])
  return { latest: sse.event, buffer: bufferRef.current, connected: sse.connected }
}
```

`MetricsCards.tsx`: large-number cards per field present in `latest`, with a unit suffix.

- [ ] **Step 1: Tests** — render with mocked SSE event sequence; assert cards reflect latest values.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): useMetricsStream hook + MetricsCards (live numbers)"
```

---

## Task 9: React — `<Sparkline>` SVG component

**Files:**
- Create: `dashboard/src/features/metrics/Sparkline.tsx`

Pure SVG. Props: `values: number[]`, `width = 120`, `height = 32`, `color = 'currentColor'`. Computes a smooth `<path d="...">` and renders. No animation in v1.

```tsx
interface SparklineProps {
  values: number[]
  width?: number
  height?: number
  color?: string
}

export function Sparkline({ values, width = 120, height = 32, color = 'currentColor' }: SparklineProps) {
  if (values.length < 2) return <svg width={width} height={height} />
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const xStep = width / (values.length - 1)
  const points = values
    .map((v, i) => `${i * xStep},${height - ((v - min) / range) * height}`)
    .join(' ')
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
    </svg>
  )
}
```

- [ ] **Step 1: Test** — render with `[1,2,3]`, assert `<polyline>` exists with three points.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): SVG Sparkline component"
```

---

## Task 10: React — `<MetricsTab>` composes cards + sparklines

**Files:**
- Create: `dashboard/src/features/metrics/MetricsTab.tsx`
- Modify: `dashboard/src/features/instance/InstancePage.tsx`

Layout:
- 3-column grid of `<MetricsCards>` showing live values from `useMetricsStream()`.
- Below: 3-column grid of `<Sparkline>` per field, drawn over the last-60 buffer.
- If `useMetricsStream().connected === false` for more than 10s: show "Metrics stream disconnected — retrying…" inline.
- If the SSE endpoint returns `INSTANCE_NOT_RUNNING` or no-metrics: render an explanation card matching the spec §9.6 matrix.

In `InstancePage.tsx`, swap the "Live metrics arrive in Plan 4" placeholder for `<MetricsTab />`.

- [ ] **Step 1: Tests** — render with mocked stream → cards + sparklines appear; render with disconnected state → message appears.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): Instance MetricsTab (live cards + sparklines)"
```

---

## Task 11: Config detail Overview tab — aggregated metrics card

**Files:**
- Modify: `dashboard/src/features/configs/ConfigDetailPage.tsx`

In the Overview tab, add a "Performance" card:
- `useQuery(['configs', id, 'metrics', 'aggregate'])` against `/api/configs/{id}/metrics/aggregate?window=7d`.
- Renders: `samples`, `total_uptime_seconds` (humanized), `avg_*` / `p50_*` / `p95_*` per field.
- Empty state: "No metrics yet — run this config to collect data."

- [ ] **Step 1: Test** — render with mocked aggregate response; assert numbers visible.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): Config detail Overview shows aggregated metrics (avg/P50/P95)"
```

---

## Task 12: Overview page — live mini-numbers when running

**Files:**
- Modify: `dashboard/src/features/overview/OverviewPage.tsx`

If `overview.instance.running === true`, the "running now" card adds two small "live" badges showing the most recent TPS + TTFT from `useMetricsStream()`. If stream isn't connected, show `—`.

- [ ] **Step 1: Test + impl + commit.**

```bash
git commit -m "feat(dashboard): Overview page shows live TPS+TTFT mini-numbers when running"
```

---

## Task 13: Update `has_metrics` in `/api/runtimes` response

**Files:**
- Modify: `src/llm_cli/webapi/routes/runtimes.py`

`RuntimeSummary.has_metrics` was hardcoded `False` in Plan 1. Update to `bool(rt.manifest_dict().get("metrics"))`.

UI can use this to enable/disable the Metrics tab pre-emptively (instead of always rendering it and showing "no live metrics" for runtimes without).

- [ ] **Step 1: Test** — assert stub-runtime has `has_metrics: false`; vllm has `true`.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(webapi): /api/runtimes summarizes manifest metrics block as has_metrics flag"
```

---

## Task 14: End-to-end smoke + PR

- [ ] **Step 1: Manual smoke**
  - Start a runtime that has `metrics:` populated (e.g., a real vLLM install).
  - `loco dashboard serve --no-open`, open browser → Instance page → start the config.
  - Within ~10s, see live cards + sparklines populate.
  - Stop the instance → cards show last values; "stream disconnected" message after 10s.
  - Visit the Config detail Overview tab → aggregated metrics visible.
- [ ] **Step 2: Stub-runtime path**
  - Start stub-runtime config → Instance Metrics tab shows "This runtime does not expose live metrics."
- [ ] **Step 3: Tests green**

```bash
uv run pytest -q
cd dashboard && npm run typecheck && npm run test && npm run build
scripts/regen-api-client.sh --check
```

- [ ] **Step 4: PR**

```bash
git push -u origin feat/web-dashboard-metrics
gh pr create --title "feat(dashboard): live metrics pipeline (Plan 4/5)" --body "..."
```

---

## Self-review

1. **Spec coverage:** §9.1 manifest schema (vllm + llamacpp + stub-runtime null), §9.2 scrape lifecycle, §9.3 failure modes (errors / timeout / parse / missing field / dashboard restart), §9.4 aggregation (avg/p50/p95/total_uptime), §9.5 retention (append-only, no rotation), §9.6 UI matrix — all covered.
2. **Placeholder scan:** none.
3. **Type consistency:** snapshot shape (`{ts, <field>: float | null, error?: str}`) consistent in tests, scrape task, aggregate, sparkline, and REST. `MetricsScrapeTask` and `MetricsScheduler` defined once in `core/metrics.py`.
4. **Branch hygiene:** `feat/web-dashboard-metrics` from `main` after Plan 3 merges.
5. **Conventional commits:** consistent throughout.
