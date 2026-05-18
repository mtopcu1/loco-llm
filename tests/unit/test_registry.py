"""Tests for manifest/config discovery and validation."""
from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from llm_cli.core import registry
from llm_cli.core.settings import save_settings


def _settings(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


def _write_runtime(
    repo: Path,
    rid: str,
    *,
    with_scripts: bool = True,
    serve_schema: dict | None = None,
    accepts_formats: list[str] | None = None,
) -> None:
    root = repo / "runtimes" / rid
    root.mkdir(parents=True)
    body = f"id: {rid}\ndisplay_name: {rid}\n"
    if accepts_formats is not None:
        body += yaml.safe_dump({"accepts_formats": accepts_formats}, sort_keys=False)
    else:
        # default for these legacy fixtures: a single stub format so configs with
        # `model:` still validate.
        body += yaml.safe_dump({"accepts_formats": ["stub"]}, sort_keys=False)
    if serve_schema is not None:
        (root / "params.yaml").write_text(
            yaml.safe_dump(serve_schema, sort_keys=False),
            encoding="utf-8",
        )
    (root / "manifest.yaml").write_text(
        body,
        encoding="utf-8",
    )
    if with_scripts:
        for name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (root / name).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def _write_model(repo: Path, mid: str, *, with_pull: bool = True) -> None:
    """Seed a model entry in the per-test registry (under data_root/models)."""
    from llm_cli.core.model_registry import (
        Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
    )
    from llm_cli.core.settings import load_settings, resolve

    settings = resolve(load_settings())
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    upsert_entry(
        settings.models_dir,
        RegistryEntry(
            id=mid,
            format="stub",
            source=HFSource(repo="o/r"),
            artifact=Artifact(
                primary="weights.bin", files=("weights.bin",), total_size_bytes=1
            ),
            metadata=Metadata(display_name=mid),
            installed_at="2026-05-17T00:00:00Z",
        ),
    )


def _write_config(
    repo: Path,
    cid: str,
    runtime: str,
    model: str,
    *,
    params: dict | None = None,
) -> None:
    (repo / "configs").mkdir(parents=True)
    body = (
        f"id: {cid}\n"
        f"runtime: {runtime}\n"
        f"model: {model}\n"
        "serve:\n"
        "  host: 127.0.0.1\n"
        "  port: 1\n"
    )
    if params is not None:
        if params:
            dumped = yaml.safe_dump(params, sort_keys=False)
            body += "  params:\n" + "".join(
                f"    {line}\n" for line in dumped.splitlines()
            )
        else:
            body += "  params: {}\n"
    (repo / "configs" / f"{cid}.yaml").write_text(
        body,
        encoding="utf-8",
    )


def test_discover_and_validate_happy_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(repo, "rt-a")
    _write_model(repo, "md-a")
    _write_config(repo, "cfg1", "rt-a", "md-a")
    cfgs = registry.discover_configs(repo)
    assert len(cfgs) == 1
    errs = registry.validate_config(repo, cfgs[0])
    assert errs == []


def test_validate_unknown_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_model(repo, "md-a")
    _write_config(repo, "cfg1", "missing-rt", "md-a")
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("unknown runtime" in e for e in errs)


def test_validate_runtime_missing_script(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(repo, "rt-a", with_scripts=False)
    _write_model(repo, "md-a")
    _write_config(repo, "cfg1", "rt-a", "md-a")
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("missing build.sh" in e for e in errs)


def test_validate_includes_settings_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    # Runtime with empty accepts_formats so the config doesn't need `model:`.
    _write_runtime(repo, "rt-a", accepts_formats=[])
    (repo / "configs").mkdir()
    (repo / "configs" / "cfg1.yaml").write_text(
        "id: cfg1\nruntime: rt-a\nserve:\n  host: 127.0.0.1\n  port: 1\n",
        encoding="utf-8",
    )
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("settings:" in e for e in errs)


def test_runtime_manifest_typed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "runtimes" / "rt-a").mkdir(parents=True)
    (repo / "runtimes" / "rt-a" / "manifest.yaml").write_text(
        "id: rt-a\n"
        "display_name: A\n"
        "official: true\n"
        "build:\n"
        "  flavor:\n"
        "    type: enum\n"
        "    values: [cuda, cpu]\n"
        "    default: cuda\n"
        "requires:\n"
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: 'v ([\\d.]+)', min: '3.16' }\n"
        "    install_hint: apt install cmake\n",
        encoding="utf-8",
    )
    (repo / "runtimes" / "rt-a" / "params.yaml").write_text(
        "ctx:\n"
        "  type: int\n"
        "  default: 8192\n",
        encoding="utf-8",
    )
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (repo / "runtimes" / "rt-a" / s).write_text(
            "#!/usr/bin/env bash\n", encoding="utf-8"
        )
    mfs = registry.load_runtime_manifests(repo)
    assert len(mfs) == 1
    rt = mfs[0]
    assert rt.id == "rt-a"
    assert rt.official is True
    assert rt.kind == "official"
    assert [s.key for s in rt.build_schema] == ["flavor"]
    assert rt.build_schema[0].values == ("cuda", "cpu")
    assert [s.key for s in rt.serve_schema] == ["ctx"]
    assert len(rt.requires) == 1
    assert rt.requires[0]["id"] == "cmake"


def test_validate_config_rejects_unknown_param(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(
        repo,
        "rt-a",
        serve_schema={"ctx": {"type": "int", "default": 8}},
    )
    _write_model(repo, "md-a")
    _write_config(repo, "c1", "rt-a", "md-a", params={"ctxx": 16})
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("unknown param" in e and "ctxx" in e for e in errs)


def test_validate_config_required_param_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(
        repo,
        "rt-a",
        serve_schema={"gguf": {"type": "string", "required": True}},
    )
    _write_model(repo, "md-a")
    _write_config(repo, "c1", "rt-a", "md-a", params={})
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("required" in e for e in errs)


def test_validate_config_warns_uninstalled_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(
        repo,
        "rt-a",
        serve_schema={"ctx": {"type": "int", "default": 8}},
    )
    _write_model(repo, "md-a")
    _write_config(repo, "c1", "rt-a", "md-a", params={"ctx": 16})
    cfg = registry.discover_configs(repo)[0]
    errs, warnings = registry.validate_config_v2(repo, cfg)
    assert errs == []
    assert any("not installed" in w for w in warnings)


def _write_runtime_manifest(repo: Path, rid: str, body: dict) -> None:
    rt = repo / "runtimes" / rid
    rt.mkdir(parents=True, exist_ok=True)
    (rt / "manifest.yaml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    for n in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / n).write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def test_runtime_manifest_accepts_formats_default_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True})
    mf = registry.get_runtime_manifest(repo, "rt")
    assert mf.accepts_formats == ()


def test_runtime_manifest_accepts_formats_list(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["gguf"]}
    )
    mf = registry.get_runtime_manifest(repo, "rt")
    assert mf.accepts_formats == ("gguf",)


def test_runtime_manifest_accepts_formats_invalid_type(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": "gguf"}
    )
    with pytest.raises(ValueError, match="accepts_formats must be a list"):
        registry.get_runtime_manifest(repo, "rt")


def _write_v2_config(repo: Path, cid: str, body: dict) -> None:
    p = repo / "configs" / f"{cid}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_validate_requires_model_when_accepts_formats_non_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["gguf"]})
    _write_v2_config(repo, "c", {
        "id": "c", "runtime": "rt",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    cfg = next(c for c in registry.discover_configs(repo) if c.id == "c")
    errs, _ = registry.validate_config_v2(repo, cfg)
    assert any("model: is required" in e for e in errs)


def test_validate_rejects_model_when_accepts_formats_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True, "accepts_formats": []})
    _write_v2_config(repo, "c", {
        "id": "c", "runtime": "rt", "model": "x",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    cfg = next(c for c in registry.discover_configs(repo) if c.id == "c")
    errs, _ = registry.validate_config_v2(repo, cfg)
    assert any("must not set `model:`" in e for e in errs)


def test_validate_errors_on_unknown_model(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["gguf"]}
    )
    _write_v2_config(repo, "c", {
        "id": "c", "runtime": "rt", "model": "ghost",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    cfg = next(c for c in registry.discover_configs(repo) if c.id == "c")
    errs, _ = registry.validate_config_v2(repo, cfg)
    assert any("unknown model 'ghost'" in e for e in errs)


def test_validate_errors_on_format_mismatch(tmp_path: Path) -> None:
    from llm_cli.core.model_registry import (
        Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
    )

    repo = tmp_path / "repo"; repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["safetensors-dir"]}
    )
    _write_v2_config(repo, "c", {
        "id": "c", "runtime": "rt", "model": "g",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    upsert_entry(
        tmp_path / "data" / "models",
        RegistryEntry(
            id="g",
            format="gguf",
            source=HFSource(repo="o/r"),
            artifact=Artifact(primary="x.gguf", files=("x.gguf",), total_size_bytes=1),
            metadata=Metadata(),
            installed_at="2026-05-17T00:00:00Z",
        ),
    )
    cfg = next(c for c in registry.discover_configs(repo) if c.id == "c")
    errs, _ = registry.validate_config_v2(repo, cfg)
    assert any("format" in e and "gguf" in e for e in errs)


def test_runtime_loads_params_yaml_with_tier_and_description(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\n"
        "display_name: Demo\n"
        "accepts_formats: []\n",
        encoding="utf-8",
    )
    (rt / "params.yaml").write_text(
        "n_threads:\n"
        "  type: int\n"
        "  default: 4\n"
        "  tier: common\n"
        "  description: Number of worker threads.\n"
        "extra:\n"
        "  type: string\n"
        "  default: ''\n"
        "  tier: advanced\n"
        "  description: Pass-through flags.\n",
        encoding="utf-8",
    )

    mfs = registry.load_runtime_manifests(tmp_path)
    assert len(mfs) == 1
    schema = mfs[0].serve_schema
    by_key = {s.key: s for s in schema}
    assert by_key["n_threads"].tier == "common"
    assert by_key["n_threads"].description == "Number of worker threads."
    assert by_key["extra"].tier == "advanced"


def test_runtime_missing_params_yaml_is_empty(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\naccepts_formats: []\n", encoding="utf-8"
    )
    mfs = registry.load_runtime_manifests(tmp_path)
    assert mfs[0].serve_schema == []


def test_runtime_manifest_with_inline_serve_is_rejected(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\naccepts_formats: []\n"
        "serve:\n  n: { type: int, default: 1 }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="serve: schema moved to params.yaml"):
        registry.load_runtime_manifests(tmp_path)


def test_runtime_manifest_kind_defaults_to_official(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\naccepts_formats: []\n", encoding="utf-8"
    )
    mfs = registry.load_runtime_manifests(tmp_path)
    assert mfs[0].kind == "official"
    assert mfs[0].official is True


def test_runtime_manifest_kind_custom_is_respected(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: custom\naccepts_formats: [gguf]\n",
        encoding="utf-8",
    )
    mfs = registry.load_runtime_manifests(tmp_path)
    assert mfs[0].kind == "custom"
    assert mfs[0].official is False


def test_runtime_manifest_kind_takes_precedence_over_official_bool(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: custom\nofficial: true\n"
        "accepts_formats: []\n",
        encoding="utf-8",
    )
    mfs = registry.load_runtime_manifests(tmp_path)
    assert mfs[0].kind == "custom"
    assert mfs[0].official is False


def test_custom_kind_forbids_build_section(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: custom\naccepts_formats: []\n"
        "build:\n"
        "  flavor: { type: enum, values: [a, b], default: a }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="custom runtimes must not declare a build section"):
        registry.load_runtime_manifests(tmp_path)


def test_unknown_kind_value_is_rejected(tmp_path: Path) -> None:
    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: weird\naccepts_formats: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="kind must be one of"):
        registry.load_runtime_manifests(tmp_path)
