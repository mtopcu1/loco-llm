"""Discover and load runtimes, models, configs, and benchmarks from the repo layout."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from llm_cli.core.install_record import is_installed
from llm_cli.core.params import ParamSpec, parse_schema, validate_params
from llm_cli.core.scaffold import scaffold_root, user_configs_dir
from llm_cli.core.settings import (
    MissingSettingError,
    UnknownSettingError,
    load_settings,
    resolve,
    resolve_settings,
)


AssetSource = Literal["scaffold", "user"]


@dataclass(frozen=True)
class RuntimeRecord:
    id: str
    path: Path
    manifest: dict[str, Any]
    source: AssetSource = "scaffold"


@dataclass(frozen=True)
class RuntimeManifest:
    id: str
    display_name: str
    description: str
    official: bool
    kind: str
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
    source: AssetSource = "scaffold"


@dataclass(frozen=True)
class ConfigRecord:
    id: str
    path: Path
    data: dict[str, Any]
    source: AssetSource = "scaffold"


def _safe_load(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return raw


_VALID_KINDS = ("official", "custom")


def _resolve_kind(data: dict[str, Any], runtime_id: str) -> str:
    if "kind" in data:
        kind = str(data["kind"])
        if kind not in _VALID_KINDS:
            raise ValueError(
                f"{runtime_id}: kind must be one of {_VALID_KINDS}; got {kind!r}"
            )
        return kind
    if "official" in data:
        return "official" if bool(data["official"]) else "custom"
    return "official"


def discover_runtimes(repo: Path, *, source: AssetSource = "scaffold") -> list[RuntimeRecord]:
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
        out.append(RuntimeRecord(id=rid, path=child, manifest=data, source=source))
    return out


def discover_benchmarks(repo: Path, *, source: AssetSource = "scaffold") -> list[BenchmarkRecord]:
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
        out.append(BenchmarkRecord(id=bid, path=child, bench=data, source=source))
    return out


def discover_configs(repo: Path, *, source: AssetSource = "scaffold") -> list[ConfigRecord]:
    root = repo / "configs"
    if not root.is_dir():
        return []
    out: list[ConfigRecord] = []
    for path in sorted(root.glob("*.yaml"), key=lambda p: p.name):
        data = _safe_load(path)
        cid = str(data.get("id", path.stem))
        out.append(ConfigRecord(id=cid, path=path, data=data, source=source))
    return out


def discover_runtimes_merged() -> list[RuntimeRecord]:
    from llm_cli.core.scaffold import scaffold_root, user_assets_root

    settings = resolve(load_settings())
    scaffold = scaffold_root()
    user = user_assets_root(settings)
    by_id: dict[str, RuntimeRecord] = {}
    scaffold_ids: set[str] = set()
    for rec in discover_runtimes(scaffold, source="scaffold"):
        by_id[rec.id] = rec
        scaffold_ids.add(rec.id)
    for rec in discover_runtimes(user, source="user"):
        by_id[rec.id] = rec
    return [by_id[k] for k in sorted(by_id)]


def discover_configs_merged() -> list[ConfigRecord]:
    from llm_cli.core.scaffold import scaffold_root, user_assets_root

    settings = resolve(load_settings())
    scaffold = scaffold_root()
    user = user_assets_root(settings)
    by_id: dict[str, ConfigRecord] = {}
    for rec in discover_configs(scaffold, source="scaffold"):
        by_id[rec.id] = rec
    for rec in discover_configs(user, source="user"):
        by_id[rec.id] = rec
    return [by_id[k] for k in sorted(by_id)]


def discover_benchmarks_merged() -> list[BenchmarkRecord]:
    from llm_cli.core.scaffold import scaffold_root, user_assets_root

    settings = resolve(load_settings())
    scaffold = scaffold_root()
    user = user_assets_root(settings)
    by_id: dict[str, BenchmarkRecord] = {}
    for rec in discover_benchmarks(scaffold, source="scaffold"):
        by_id[rec.id] = rec
    for rec in discover_benchmarks(user, source="user"):
        by_id[rec.id] = rec
    return [by_id[k] for k in sorted(by_id)]


def runtime_overrides_scaffold(runtime_id: str) -> bool:
    """True when a user-layer runtime shadows a scaffold id."""
    from llm_cli.core.scaffold import scaffold_root, user_assets_root

    settings = resolve(load_settings())
    user = user_assets_root(settings) / "runtimes" / runtime_id
    scaffold = scaffold_root() / "runtimes" / runtime_id
    return user.is_dir() and scaffold.is_dir()


def get_runtime(repo: Path, runtime_id: str) -> RuntimeRecord | None:
    for r in discover_runtimes(repo):
        if r.id == runtime_id:
            return r
    return None


def get_runtime_merged(runtime_id: str) -> RuntimeRecord | None:
    for r in discover_runtimes_merged():
        if r.id == runtime_id:
            return r
    return None


def _to_manifest(rec: RuntimeRecord) -> RuntimeManifest:
    data = rec.manifest
    if "serve" in data:
        raise ValueError(
            f"{rec.id}: serve: schema moved to params.yaml; "
            f"move the keys to {rec.path / 'params.yaml'}"
        )
    kind = _resolve_kind(data, rec.id)
    if kind == "custom" and "build" in data:
        raise ValueError(f"{rec.id}: custom runtimes must not declare a build section")

    requires = data.get("requires") or []
    if not isinstance(requires, list):
        raise ValueError(f"{rec.id}: requires must be a list")
    raw_formats = data.get("accepts_formats", [])
    if not isinstance(raw_formats, list):
        raise ValueError(f"{rec.id}: accepts_formats must be a list of strings")
    accepts_formats = tuple(str(f) for f in raw_formats)

    params_path = rec.path / "params.yaml"
    if params_path.is_file():
        raw_params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        params_raw: dict[str, Any] = {} if raw_params is None else raw_params
        if not isinstance(params_raw, dict):
            raise ValueError(f"{rec.id}: {params_path}: top-level must be a mapping")
        serve_schema = parse_schema(params_raw)
    else:
        serve_schema = []

    return RuntimeManifest(
        id=rec.id,
        display_name=str(data.get("display_name", rec.id)),
        description=str(data.get("description", "")),
        official=(kind == "official"),
        kind=kind,
        build_schema=parse_schema(data.get("build") or {}),
        serve_schema=serve_schema,
        requires=[r for r in requires if isinstance(r, dict)],
        accepts_formats=accepts_formats,
        path=rec.path,
        raw=data,
    )


def load_runtime_manifests(repo: Path) -> list[RuntimeManifest]:
    return [_to_manifest(r) for r in discover_runtimes(repo)]


def load_runtime_manifests_merged() -> list[RuntimeManifest]:
    return [_to_manifest(r) for r in discover_runtimes_merged()]


def get_runtime_manifest(repo: Path, runtime_id: str) -> RuntimeManifest | None:
    rec = get_runtime(repo, runtime_id)
    return _to_manifest(rec) if rec is not None else None


def get_runtime_manifest_merged(runtime_id: str) -> RuntimeManifest | None:
    rec = get_runtime_merged(runtime_id)
    return _to_manifest(rec) if rec is not None else None


def get_config(repo: Path, config_id: str) -> ConfigRecord | None:
    for c in discover_configs(repo):
        if c.id == config_id:
            return c
    return None


def get_config_merged(config_id: str) -> ConfigRecord | None:
    for c in discover_configs_merged():
        if c.id == config_id:
            return c
    return None


def validate_runtime_layout(r: RuntimeRecord) -> list[str]:
    errs: list[str] = []
    kind = _resolve_kind(r.manifest, r.id)
    scripts = ["serve.sh", "healthcheck.sh"]
    if kind == "official":
        scripts.insert(0, "build.sh")
    for name in scripts:
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

    rt = get_runtime_merged(rt_id)
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


class ConfigAlreadyExistsError(ValueError):
    pass


class ConfigValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class ConfigNotFoundInUserLayerError(ValueError):
    pass


def _atomic_write_yaml(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".cfg-", suffix=".yaml", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def write_config(data: dict[str, Any], *, overwrite: bool = False) -> ConfigRecord:
    """Write a config to the user layer after validation."""
    config_id = str(data.get("id", "")).strip()
    if not config_id:
        raise ConfigValidationError(["id is required"])

    if get_config_merged(config_id) is not None and not overwrite:
        raise ConfigAlreadyExistsError(f"config {config_id!r} already exists")

    settings = resolve_settings()
    out_path = user_configs_dir(settings) / f"{config_id}.yaml"
    doc = dict(data)
    doc["id"] = config_id
    cfg = ConfigRecord(id=config_id, path=out_path, data=doc, source="user")
    errors, _warnings = validate_config_v2(scaffold_root(), cfg)
    if errors:
        raise ConfigValidationError(errors)

    _atomic_write_yaml(out_path, doc)
    from llm_cli.core.lifecycle import append_history, state_root

    append_history(
        state_root(settings),
        {
            "action": "config-create" if not overwrite else "config-update",
            "id": config_id,
            "via": "dashboard",
        },
    )
    return cfg


def delete_config(config_id: str) -> None:
    """Delete a user-layer config file."""
    settings = resolve_settings()
    out_path = user_configs_dir(settings) / f"{config_id}.yaml"
    if not out_path.is_file():
        raise ConfigNotFoundInUserLayerError(f"config {config_id!r} not found in user layer")
    out_path.unlink()
    from llm_cli.core.lifecycle import append_history, state_root

    append_history(
        state_root(settings),
        {"action": "config-delete", "id": config_id, "via": "dashboard"},
    )
