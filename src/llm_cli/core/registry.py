"""Discover and load runtimes, models, configs, and benchmarks from the repo layout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from llm_cli.core.install_record import is_installed
from llm_cli.core.params import ParamSpec, parse_schema, validate_params
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
class RuntimeManifest:
    id: str
    display_name: str
    description: str
    official: bool
    build_schema: list[ParamSpec]
    serve_schema: list[ParamSpec]
    requires: list[dict[str, Any]]
    accepts_formats: tuple[str, ...]
    path: Path
    raw: dict[str, Any]


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


def _to_manifest(rec: RuntimeRecord) -> RuntimeManifest:
    data = rec.manifest
    requires = data.get("requires") or []
    if not isinstance(requires, list):
        raise ValueError(f"{rec.id}: requires must be a list")
    raw_formats = data.get("accepts_formats", [])
    if not isinstance(raw_formats, list):
        raise ValueError(f"{rec.id}: accepts_formats must be a list of strings")
    accepts_formats = tuple(str(f) for f in raw_formats)
    return RuntimeManifest(
        id=rec.id,
        display_name=str(data.get("display_name", rec.id)),
        description=str(data.get("description", "")),
        official=bool(data.get("official", False)),
        build_schema=parse_schema(data.get("build") or {}),
        serve_schema=parse_schema(data.get("serve") or {}),
        requires=[r for r in requires if isinstance(r, dict)],
        accepts_formats=accepts_formats,
        path=rec.path,
        raw=data,
    )


def load_runtime_manifests(repo: Path) -> list[RuntimeManifest]:
    return [_to_manifest(r) for r in discover_runtimes(repo)]


def get_runtime_manifest(repo: Path, runtime_id: str) -> RuntimeManifest | None:
    rec = get_runtime(repo, runtime_id)
    return _to_manifest(rec) if rec is not None else None


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


def validate_config_v2(repo: Path, cfg: ConfigRecord) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors fail validation; warnings are advisory."""
    errs: list[str] = []
    warnings: list[str] = []

    rt_id = cfg.data.get("runtime")
    if not isinstance(rt_id, str):
        errs.append(f"{cfg.id}: runtime must be a string")
        return errs, warnings

    rt = get_runtime(repo, rt_id)
    rt_manifest = _to_manifest(rt) if rt is not None else None
    if rt is None:
        errs.append(f"{cfg.id}: unknown runtime {rt_id!r}")
    else:
        errs.extend(validate_runtime_layout(rt))

    md_id_raw = cfg.data.get("model")
    md_id: str | None = md_id_raw if isinstance(md_id_raw, str) else None
    if rt_manifest is not None:
        if rt_manifest.accepts_formats and md_id is None:
            errs.append(
                f"{cfg.id}: model: is required when runtime {rt_id!r} declares "
                f"accepts_formats={list(rt_manifest.accepts_formats)}"
            )
        if not rt_manifest.accepts_formats and md_id is not None:
            errs.append(
                f"{cfg.id}: runtime {rt_id!r} has empty accepts_formats; "
                f"config must not set `model:`"
            )

    serve = cfg.data.get("serve")
    if not isinstance(serve, dict):
        errs.append(f"{cfg.id}: serve must be a mapping")
    else:
        for key in ("host", "port"):
            if key not in serve:
                errs.append(f"{cfg.id}: serve.{key} is required")
        if rt_manifest is not None:
            params = serve.get("params", {})
            if not isinstance(params, dict):
                errs.append(f"{cfg.id}: serve.params must be a mapping")
            else:
                _, param_errs = validate_params(rt_manifest.serve_schema, params)
                errs.extend(f"{cfg.id}: {e}" for e in param_errs)

    ready = cfg.data.get("readiness")
    if ready is not None and not isinstance(ready, dict):
        errs.append(f"{cfg.id}: readiness must be a mapping when present")

    yaml_id = cfg.data.get("id")
    if yaml_id is not None and yaml_id != cfg.id:
        errs.append(f"{cfg.id}: file id {yaml_id!r} does not match filename/config id")

    try:
        settings = resolve(load_settings())
    except (MissingSettingError, UnknownSettingError, ValueError) as exc:
        errs.append(f"settings: {exc}")
        return errs, warnings

    if rt_manifest is not None and md_id is not None and rt_manifest.accepts_formats:
        from llm_cli.core.model_registry import get_entry as _get_model

        model_entry = _get_model(settings.models_dir, md_id)
        if model_entry is None:
            errs.append(f"{cfg.id}: unknown model {md_id!r}")
        else:
            if model_entry.format not in rt_manifest.accepts_formats:
                errs.append(
                    f"{cfg.id}: model {md_id!r} has format "
                    f"{model_entry.format!r}; runtime {rt_id!r} accepts "
                    f"{list(rt_manifest.accepts_formats)}"
                )
            primary_path = settings.models_dir / md_id / model_entry.artifact.primary
            if not primary_path.exists():
                warnings.append(
                    f"{cfg.id}: model {md_id!r} primary path missing on disk "
                    f"({primary_path}); run `llm model pull {md_id}`."
                )

    if rt_manifest is not None and not is_installed(settings.runtimes_dir, rt_id):
        warnings.append(
            f"{cfg.id}: runtime {rt_id!r} is not installed; "
            f"run `llm runtime install {rt_id}` before `llm serve`."
        )

    return errs, warnings


def validate_config(repo: Path, cfg: ConfigRecord) -> list[str]:
    errors, _ = validate_config_v2(repo, cfg)
    return errors
