"""Discover and load runtimes, models, configs, and benchmarks from the repo layout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from llm_cli.core.settings import (
    MissingSettingError,
    UnknownSettingError,
    load_settings,
    resolve,
)


@dataclass(frozen=True)
class RuntimeRecord:
    id: str
    path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class ModelRecord:
    id: str
    path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class BenchmarkRecord:
    id: str
    path: Path
    bench: dict[str, Any]


@dataclass(frozen=True)
class ConfigRecord:
    id: str
    path: Path
    data: dict[str, Any]


def _safe_load(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return raw


def discover_runtimes(repo: Path) -> list[RuntimeRecord]:
    root = repo / "runtimes"
    if not root.is_dir():
        return []
    out: list[RuntimeRecord] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        mf = child / "manifest.yaml"
        if not mf.is_file():
            continue
        data = _safe_load(mf)
        rid = str(data.get("id", child.name))
        out.append(RuntimeRecord(id=rid, path=child, manifest=data))
    return out


def discover_models(repo: Path) -> list[ModelRecord]:
    root = repo / "models"
    if not root.is_dir():
        return []
    out: list[ModelRecord] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        mf = child / "manifest.yaml"
        if not mf.is_file():
            continue
        data = _safe_load(mf)
        mid = str(data.get("id", child.name))
        out.append(ModelRecord(id=mid, path=child, manifest=data))
    return out


def discover_benchmarks(repo: Path) -> list[BenchmarkRecord]:
    root = repo / "benchmarks"
    if not root.is_dir():
        return []
    out: list[BenchmarkRecord] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        bf = child / "bench.yaml"
        if not bf.is_file():
            continue
        data = _safe_load(bf)
        bid = str(data.get("id", child.name))
        out.append(BenchmarkRecord(id=bid, path=child, bench=data))
    return out


def discover_configs(repo: Path) -> list[ConfigRecord]:
    root = repo / "configs"
    if not root.is_dir():
        return []
    out: list[ConfigRecord] = []
    for path in sorted(root.glob("*.yaml"), key=lambda p: p.name):
        data = _safe_load(path)
        cid = str(data.get("id", path.stem))
        out.append(ConfigRecord(id=cid, path=path, data=data))
    return out


def get_runtime(repo: Path, runtime_id: str) -> RuntimeRecord | None:
    for r in discover_runtimes(repo):
        if r.id == runtime_id:
            return r
    return None


def get_model(repo: Path, model_id: str) -> ModelRecord | None:
    for m in discover_models(repo):
        if m.id == model_id:
            return m
    return None


def get_config(repo: Path, config_id: str) -> ConfigRecord | None:
    for c in discover_configs(repo):
        if c.id == config_id:
            return c
    return None


def validate_runtime_layout(r: RuntimeRecord) -> list[str]:
    errs: list[str] = []
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        if not (r.path / name).is_file():
            errs.append(f"{r.id}: missing {name}")
    return errs


def validate_model_layout(m: ModelRecord) -> list[str]:
    errs: list[str] = []
    if not (m.path / "pull.sh").is_file():
        errs.append(f"{m.id}: missing pull.sh")
    return errs


def validate_config(
    repo: Path, cfg: ConfigRecord
) -> list[str]:
    errs: list[str] = []
    rt_id = cfg.data.get("runtime")
    md_id = cfg.data.get("model")
    if not isinstance(rt_id, str):
        errs.append(f"{cfg.id}: runtime must be a string")
        return errs
    if not isinstance(md_id, str):
        errs.append(f"{cfg.id}: model must be a string")
        return errs
    rt = get_runtime(repo, rt_id)
    if rt is None:
        errs.append(f"{cfg.id}: unknown runtime {rt_id!r}")
    else:
        errs.extend(validate_runtime_layout(rt))
    md = get_model(repo, md_id)
    if md is None:
        errs.append(f"{cfg.id}: unknown model {md_id!r}")
    else:
        errs.extend(validate_model_layout(md))
    serve = cfg.data.get("serve")
    if not isinstance(serve, dict):
        errs.append(f"{cfg.id}: serve must be a mapping")
    else:
        for key in ("host", "port"):
            if key not in serve:
                errs.append(f"{cfg.id}: serve.{key} is required")
    ready = cfg.data.get("readiness")
    if ready is not None and not isinstance(ready, dict):
        errs.append(f"{cfg.id}: readiness must be a mapping when present")
    yaml_id = cfg.data.get("id")
    if yaml_id is not None and yaml_id != cfg.id:
        errs.append(f"{cfg.id}: file id {yaml_id!r} does not match filename/config id")
    try:
        resolve(load_settings())
    except (MissingSettingError, UnknownSettingError, ValueError) as exc:
        errs.append(f"settings: {exc}")
    return errs
