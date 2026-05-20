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
