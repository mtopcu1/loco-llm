"""Integration tests for list, config, build, and pull commands."""
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
        "serve:\n"
        "  weights:\n"
        "    type: path\n"
        "    env: LLM_RT_A_WEIGHTS\n",
        encoding="utf-8",
    )
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / name).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    md = repo / "models" / "md-a"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text("id: md-a\ndisplay_name: M\n", encoding="utf-8")
    (md / "pull.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    (repo / "configs").mkdir()
    (repo / "configs" / "cfg-one.yaml").write_text(
        "id: cfg-one\n"
        "runtime: rt-a\n"
        "model: md-a\n"
        "serve:\n"
        "  host: 127.0.0.1\n"
        "  port: 9\n"
        "  env:\n"
        "    X: ${data_root}/mark\n"
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
    assert "/mark" in result.stdout
    assert "/m.gguf" in result.stdout


@patch("llm_cli.commands.artifacts.run_repo_bash", return_value=0)
def test_build_calls_run_repo_bash(mock_run, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["build", "rt-a"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args[0][1] == "runtimes/rt-a/build.sh"


@patch("llm_cli.commands.artifacts.run_repo_bash", return_value=0)
def test_pull_calls_run_repo_bash(mock_run, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["pull", "md-a"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args[0][1] == "models/md-a/pull.sh"


def test_build_unknown_runtime_errors(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _configure(tmp_path, repo)
    result = runner.invoke(
        app,
        ["build", "missing"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
