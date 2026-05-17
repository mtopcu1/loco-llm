from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    upsert_entry,
)
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _seed_entry(models_dir: Path, mid: str = "qwen-qwen2.5-7b-instruct") -> RegistryEntry:
    e = RegistryEntry(
        id=mid,
        format="safetensors-dir",
        source=HFSource(repo="Qwen/Qwen2.5-7B-Instruct"),
        artifact=Artifact(primary=".", files=("config.json",), total_size_bytes=42),
        metadata=Metadata(display_name="Qwen 2.5", license="apache-2.0"),
        installed_at="2026-05-17T00:00:00Z",
    )
    upsert_entry(models_dir, e)
    return e


def _configure(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    return tmp_path / "data" / "models"


def test_model_list_empty(tmp_path: Path) -> None:
    _configure(tmp_path)
    result = runner.invoke(app, ["model", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "no models registered" in result.stdout.lower() or "Models" in result.stdout


def test_model_list_shows_registered_entry(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir)
    result = runner.invoke(app, ["model", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "qwen-qwen2.5-7b-instruct" in result.stdout
    assert "safetensors-dir" in result.stdout


def test_model_info(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir)
    result = runner.invoke(
        app, ["model", "info", "qwen-qwen2.5-7b-instruct"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert "Qwen/Qwen2.5-7B-Instruct" in result.stdout
    assert "apache-2.0" in result.stdout


def test_model_info_missing(tmp_path: Path) -> None:
    _configure(tmp_path)
    result = runner.invoke(app, ["model", "info", "ghost"], catch_exceptions=False)
    assert result.exit_code == 1
    assert "unknown model" in result.stdout
