"""Live metrics scrape, JSONL persistence, and pure-Python aggregation."""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
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
    return {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }[m.group(2)]


def _parse_label_filter(query: str) -> tuple[str, dict[str, str]]:
    """`vllm:foo{phase="decode",model="a"}` → ("vllm:foo", {phase: decode, model: a})"""
    if "{" not in query:
        return query, {}
    name, rest = query.split("{", 1)
    rest = rest.rstrip("}")
    labels: dict[str, str] = {}
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

    def gen() -> Iterator[dict]:
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
                        ts = datetime.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                            tzinfo=UTC
                        )
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
    from llm_cli.core.lifecycle import read_history, state_root

    try:
        events = read_history(state_root(resolve_settings()))
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


def sparkline(config_id: str, *, bucket: str = "5m", window: str = "24h") -> list[dict]:
    since = datetime.now(tz=UTC) - _parse_window(window)
    bucket_td = _parse_window(bucket)
    snaps = [s for s in read_snapshots(config_id, since=since) if "error" not in s]
    if not snaps:
        return []
    field_keys = {
        k for s in snaps for k in s if k != "ts" and isinstance(s.get(k), (int, float))
    }
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
        point: dict = {"ts": ts}
        for f, vals in buckets[idx].items():
            point[f] = sum(vals) / len(vals) if vals else None
        out.append(point)
    return out


# --- Scrape task + scheduler -------------------------------------------------

import asyncio
import logging

import httpx

logger = logging.getLogger("llm_cli.core.metrics")


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class MetricsScrapeTask:
    def __init__(
        self,
        *,
        config_id: str,
        runtime_id: str,
        manifest_metrics: dict,
        host: str,
        port: int,
        hub,
        interval_seconds: float = 5.0,
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
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())

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
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning("metrics parse error for %s: %s", self.config_id, e)
                    snap = {"ts": _now_iso(), "error": "parse"}
                    append_snapshot(self.config_id, snap)
                    self.hub.publish(snap)
                    self._consec_errors += 1

                if self._consec_errors >= 3:
                    await asyncio.sleep(60.0)
                    self._consec_errors = 0
                else:
                    await asyncio.sleep(self.interval_seconds)


class MetricsScheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, MetricsScrapeTask] = {}
        self._hubs: dict[str, object] = {}

    def hub_for(self, config_id: str):
        from llm_cli.webapi.streams import EventHub

        h = self._hubs.get(config_id)
        if h is None:
            h = EventHub[dict]()
            self._hubs[config_id] = h
        return h

    async def on_instance_started(
        self, config_id: str, runtime_id: str, host: str, port: int
    ) -> None:
        from llm_cli.core import registry

        rt = registry.get_runtime_merged(runtime_id)
        if rt is None:
            return
        manifest_metrics = rt.manifest.get("metrics")
        if not manifest_metrics:
            return
        if config_id in self._tasks:
            await self._tasks[config_id].stop()
        task = MetricsScrapeTask(
            config_id=config_id,
            runtime_id=runtime_id,
            manifest_metrics=manifest_metrics,
            host=host,
            port=port,
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


async def handle_lifecycle_event(ev: dict) -> None:
    """Start/stop scrape tasks in response to lifecycle bus events."""
    action = ev.get("action")
    if action == "start":
        runtime_id = ev.get("runtime_id")
        port = ev.get("port")
        config_id = ev.get("config_id")
        if not config_id or not runtime_id or port is None:
            return
        await scheduler().on_instance_started(
            config_id=str(config_id),
            runtime_id=str(runtime_id),
            host="127.0.0.1",
            port=int(port),
        )
    elif action == "stop":
        config_id = ev.get("config_id")
        if config_id:
            await scheduler().on_instance_stopped(str(config_id))
    elif action == "switch":
        old_id = ev.get("from")
        if old_id:
            await scheduler().on_instance_stopped(str(old_id))
