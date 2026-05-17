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


from unittest.mock import patch

from llm_cli.core.hf_client import HFRepoInfo, HFSibling


def _fake_repo_info() -> HFRepoInfo:
    return HFRepoInfo(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        sha="abc",
        license="apache-2.0",
        siblings=[
            HFSibling(
                rfilename="Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf",
                size=100,
                lfs_sha256="111",
            ),
            HFSibling(
                rfilename="Qwen3.6-235B-A22B-UD-Q4_K_XL-00002-of-00002.gguf",
                size=200,
                lfs_sha256="222",
            ),
            HFSibling(rfilename="README.md", size=10, lfs_sha256=None),
        ],
    )


def _fake_download(repo, revision, include, exclude, target_dir):
    for name in (
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf",
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00002-of-00002.gguf",
    ):
        p = Path(target_dir) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * (100 if "00001" in name else 200))
    return 0


def test_model_pull_url_happy_path(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    url = (
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/"
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf"
    )
    with patch(
        "llm_cli.commands.model_cmd.fetch_repo_revision", return_value=_fake_repo_info()
    ), patch(
        "llm_cli.commands.model_cmd.hf_download", side_effect=_fake_download
    ), patch(
        "llm_cli.commands.model_cmd._verify_sha256", return_value=[]
    ):
        result = runner.invoke(app, ["model", "pull", url], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "unsloth-qwen3.6-235b-a22b__ud-q4-k-xl")
    assert e is not None
    assert e.format == "gguf"
    assert e.source.kind == "hf"
    assert e.source.repo == "unsloth/Qwen3.6-235B-A22B-GGUF"
    assert e.artifact.primary == "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf"
    assert len(e.artifact.files) == 2
