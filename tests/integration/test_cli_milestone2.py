"""Integration tests for list, config, runtime install, and model pull."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _configure(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


def _make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    rt = repo / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: rt-a\n"
        "display_name: A\n"
        "official: true\n"
        "accepts_formats: [stub]\n"
        "build: {}\n",
        encoding="utf-8",
    )
    (rt / "params.yaml").write_text(
        "weights:\n"
        "  type: path\n"
        "  env: LLM_RT_A_WEIGHTS\n",
        encoding="utf-8",
    )
    for name in ("build.sh", "serve.sh", "healthcheck.sh", "verify.sh"):
        (rt / name).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")

    # Seed model registry: same scaffolding tests expect a 'md-a' model present.
    from llm_cli.core.model_registry import (
        Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
    )
    models_dir = root / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "md-a").mkdir(parents=True, exist_ok=True)
    (models_dir / "md-a" / "weights.bin").write_bytes(b"x")
    upsert_entry(
        models_dir,
        RegistryEntry(
            id="md-a",
            format="stub",
            source=HFSource(repo="o/r"),
            artifact=Artifact(primary="weights.bin", files=("weights.bin",), total_size_bytes=1),
            metadata=Metadata(display_name="M"),
            installed_at="2026-05-17T00:00:00Z",
        ),
    )

    (repo / "configs").mkdir()
    (repo / "configs" / "cfg-one.yaml").write_text(
        "id: cfg-one\n"
        "runtime: rt-a\n"
        "model: md-a\n"
        "serve:\n"
        "  host: 127.0.0.1\n"
        "  port: 9\n"
        "  params:\n"
        "    weights: ${models_dir}/m.gguf\n",
        encoding="utf-8",
    )
    bench = repo / "benchmarks" / "bench-a"
    bench.mkdir(parents=True)
    (bench / "bench.yaml").write_text("id: bench-a\nneeds_server: false\n", encoding="utf-8")
    return repo


def test_list_runtimes_table(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["list", "runtimes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "rt-a" in result.stdout


def test_list_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["list", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert '"id": "rt-a"' in result.stdout
    assert '"kind": "runtime"' in result.stdout


def test_list_invalid_kind_errors(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["list", "nope"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1


def test_config_validate_ok(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["config", "validate"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "ok" in result.stdout
    assert "cfg-one" in result.stdout


def test_config_show_resolves_env(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["config", "show", "cfg-one"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "${data_root}" not in result.stdout
    assert "${models_dir}" not in result.stdout
    assert "/m.gguf" in result.stdout


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_install_calls_build_and_verify(
    mock_verify, mock_build, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["runtime", "install", "rt-a", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    mock_build.assert_called_once()
    mock_verify.assert_called_once()
    assert mock_build.call_args.kwargs["runtime_id"] == "rt-a"
    assert mock_verify.call_args.kwargs["runtime_id"] == "rt-a"


def test_runtime_install_unknown_runtime_errors(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["runtime", "install", "missing", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
