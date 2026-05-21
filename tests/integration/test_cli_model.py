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
from tests.cli_helpers import cli_plain

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


def test_model_pull_existing_id_refreshes(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    (models_dir / "qwen-q__q4").mkdir(parents=True)
    (models_dir / "qwen-q__q4" / "x.gguf").write_bytes(b"x" * 50)
    from llm_cli.core.model_registry import (
        Artifact,
        HFSource,
        Metadata,
        RegistryEntry,
        get_entry,
        upsert_entry,
    )
    upsert_entry(
        models_dir,
        RegistryEntry(
            id="qwen-q__q4",
            format="gguf",
            source=HFSource(repo="qwen/Q", revision="main", include=("*Q4*",)),
            artifact=Artifact(primary="x.gguf", files=("x.gguf",), total_size_bytes=50),
            metadata=Metadata(display_name="qwen/Q"),
            installed_at="2026-01-01T00:00:00Z",
        ),
    )

    def fake_dl(repo, revision, include, exclude, target_dir):
        return 0

    with patch("llm_cli.commands.model_cmd.hf_download", side_effect=fake_dl):
        result = runner.invoke(app, ["model", "pull", "qwen-q__q4"], catch_exceptions=False)
    assert result.exit_code == 0
    e = get_entry(models_dir, "qwen-q__q4")
    assert e.installed_at != "2026-01-01T00:00:00Z"


def test_model_pull_ambiguous_url_errors(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    url = "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF"
    multi_quant = HFRepoInfo(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        sha="x",
        license=None,
        siblings=[
            HFSibling(rfilename="model-Q4_K_M.gguf", size=10, lfs_sha256=None),
            HFSibling(rfilename="model-Q5_K_M.gguf", size=10, lfs_sha256=None),
        ],
    )
    with patch(
        "llm_cli.core.model_pull.fetch_repo_revision", return_value=multi_quant
    ), patch(
        "llm_cli.core.model_pull.hf_download"
    ) as mock_dl:
        result = runner.invoke(app, ["model", "pull", url], catch_exceptions=False)
    assert result.exit_code == 1
    assert "--include" in cli_plain(result)
    assert not mock_dl.called
    from llm_cli.core.model_registry import load_registry
    assert load_registry(models_dir) == {}


def test_model_add_safetensors_dir(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    src = tmp_path / "src"; src.mkdir()
    (src / "config.json").write_text("{}", encoding="utf-8")
    (src / "tokenizer.json").write_text("{}", encoding="utf-8")
    (src / "model.safetensors").write_bytes(b"x" * 32)
    result = runner.invoke(
        app, ["model", "add", "my-ft", str(src), "--format", "safetensors-dir"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    target = models_dir / "my-ft"
    assert (target / "config.json").exists()
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "my-ft")
    assert e.format == "safetensors-dir"
    assert e.source.kind == "local"
    assert e.artifact.primary == "."


def test_model_add_gguf_single_file(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    f = tmp_path / "weights.gguf"; f.write_bytes(b"x" * 16)
    result = runner.invoke(
        app, ["model", "add", "single-q", str(f), "--format", "gguf"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    target = models_dir / "single-q"
    assert (target / "weights.gguf").exists()
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "single-q")
    assert e.artifact.primary == "weights.gguf"


def test_model_add_rejects_safetensors_dir_without_config(tmp_path: Path) -> None:
    _configure(tmp_path)
    src = tmp_path / "src"; src.mkdir()
    (src / "model.safetensors").write_bytes(b"x")
    result = runner.invoke(
        app, ["model", "add", "bad", str(src), "--format", "safetensors-dir"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "config.json" in result.stdout


def test_model_add_rejects_missing_path(tmp_path: Path) -> None:
    _configure(tmp_path)
    result = runner.invoke(
        app, ["model", "add", "x", str(tmp_path / "nope"), "--format", "gguf"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "does not exist" in result.stdout


def test_model_uninstall_removes_registry_row(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir, "x")
    (models_dir / "x").mkdir(exist_ok=True)
    (models_dir / "x" / "weights.gguf").write_bytes(b"x")
    result = runner.invoke(app, ["model", "uninstall", "x", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0
    from llm_cli.core.model_registry import get_entry
    assert get_entry(models_dir, "x") is None
    assert (models_dir / "x" / "weights.gguf").exists()


def test_model_uninstall_with_purge_removes_files(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir, "x")
    (models_dir / "x").mkdir(exist_ok=True)
    (models_dir / "x" / "weights.gguf").write_bytes(b"x")
    result = runner.invoke(
        app, ["model", "uninstall", "x", "--purge", "--yes"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert not (models_dir / "x").exists()


def test_model_uninstall_unknown_id_errors(tmp_path: Path) -> None:
    _configure(tmp_path)
    result = runner.invoke(
        app, ["model", "uninstall", "ghost", "--yes"], catch_exceptions=False
    )
    assert result.exit_code == 1
    assert "unknown model" in result.stdout


def test_model_pull_url_happy_path(tmp_path: Path) -> None:
    models_dir = _configure(tmp_path)
    url = (
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/"
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf"
    )
    with patch(
        "llm_cli.core.model_pull.fetch_repo_revision", return_value=_fake_repo_info()
    ), patch(
        "llm_cli.core.model_pull.hf_download", side_effect=_fake_download
    ), patch(
        "llm_cli.core.model_pull._verify_sha256", return_value=[]
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
