"""Tests for config display resolution."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core.registry import ConfigRecord
from llm_cli.core.settings import Settings


def test_resolve_expands_data_root_in_serve_env(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data_root = tmp_path / "data"
    raw = {
        "id": "x",
        "runtime": "r",
        "model": "m",
        "serve": {"host": "127.0.0.1", "port": 1, "env": {"K": "${data_root}/v"}},
    }
    cfg = ConfigRecord(id="x", path=repo / "configs" / "x.yaml", data=raw)
    settings = Settings(
        data_root=data_root,
        repo_root=repo,
        runtimes_dir=data_root / "runtimes",
        models_dir=data_root / "models",
        cache_dir=data_root / "cache",
    )
    out = resolve_config_for_display(cfg, settings)
    assert out["serve"]["env"]["K"] == f"{settings.data_root.as_posix()}/v"
    assert cfg.data["serve"]["env"]["K"] == "${data_root}/v"


def test_resolve_expands_templates_in_serve_params(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data_root = tmp_path / "data"
    raw = {
        "id": "x",
        "runtime": "r",
        "model": "m",
        "serve": {
            "host": "127.0.0.1",
            "port": 1,
            "params": {
                "gguf_path": "${models_dir}/model.gguf",
                "ctx": 4096,
            },
        },
    }
    cfg = ConfigRecord(id="x", path=repo / "configs" / "x.yaml", data=raw)
    settings = Settings(
        data_root=data_root,
        repo_root=repo,
        runtimes_dir=data_root / "runtimes",
        models_dir=data_root / "models",
        cache_dir=data_root / "cache",
    )
    out = resolve_config_for_display(cfg, settings)
    assert out["serve"]["params"]["gguf_path"] == (
        f"{settings.models_dir.as_posix()}/model.gguf"
    )
    assert out["serve"]["params"]["ctx"] == 4096
    assert cfg.data["serve"]["params"]["gguf_path"] == "${models_dir}/model.gguf"
