"""Tests for manifest/config discovery and validation."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core import registry
from llm_cli.core.settings import save_settings


def _settings(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


def _write_runtime(repo: Path, rid: str, *, with_scripts: bool = True) -> None:
    root = repo / "runtimes" / rid
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        f"id: {rid}\ndisplay_name: {rid}\n",
        encoding="utf-8",
    )
    if with_scripts:
        for name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (root / name).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def _write_model(repo: Path, mid: str, *, with_pull: bool = True) -> None:
    root = repo / "models" / mid
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        f"id: {mid}\ndisplay_name: {mid}\n",
        encoding="utf-8",
    )
    if with_pull:
        (root / "pull.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def _write_config(repo: Path, cid: str, runtime: str, model: str) -> None:
    (repo / "configs").mkdir(parents=True)
    (repo / "configs" / f"{cid}.yaml").write_text(
        f"id: {cid}\n"
        f"runtime: {runtime}\n"
        f"model: {model}\n"
        "serve:\n"
        "  host: 127.0.0.1\n"
        "  port: 1\n",
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
    _write_runtime(repo, "rt-a")
    _write_model(repo, "md-a")
    _write_config(repo, "cfg1", "rt-a", "md-a")
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
        "serve:\n"
        "  ctx:\n"
        "    type: int\n"
        "    default: 8192\n"
        "requires:\n"
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: 'v ([\\d.]+)', min: '3.16' }\n"
        "    install_hint: apt install cmake\n",
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
    assert [s.key for s in rt.build_schema] == ["flavor"]
    assert rt.build_schema[0].values == ("cuda", "cpu")
    assert [s.key for s in rt.serve_schema] == ["ctx"]
    assert len(rt.requires) == 1
    assert rt.requires[0]["id"] == "cmake"
