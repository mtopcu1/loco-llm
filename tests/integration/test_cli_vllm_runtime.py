from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.install_record import read_record
from llm_cli.main import app

runner = CliRunner()


def _seed_repo(tmp_path: Path, monkeypatch) -> Path:
    from llm_cli.core import repo as repo_mod
    from llm_cli.core.settings import save_settings

    workspace_root = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    shutil.copytree(workspace_root / "runtimes", tmp_path / "runtimes")
    (tmp_path / "configs").mkdir()
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(tmp_path)})
    return tmp_path


def _seed_model_registry(monkeypatch) -> None:
    from llm_cli.core import model_registry as mr
    from llm_cli.commands import config_cmd as cc

    fake_entry = mr.RegistryEntry(
        id="qwen-sf",
        format="safetensors-dir",
        source=mr.HFSource(repo="Qwen/Qwen2.5-7B-Instruct"),
        artifact=mr.Artifact(
            primary="model.safetensors",
            files=("model.safetensors",),
            total_size_bytes=8 * 1024**3,
        ),
        metadata=mr.Metadata(),
        installed_at="",
    )

    def fake_get(models_dir, eid):
        return fake_entry if eid == "qwen-sf" else None

    reg = {"qwen-sf": fake_entry}
    monkeypatch.setattr(mr, "get_entry", fake_get)
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: reg)
    monkeypatch.setattr(cc, "get_entry", fake_get)
    monkeypatch.setattr(cc, "load_registry", lambda models_dir: reg)


def test_runtime_list_includes_vllm(monkeypatch, tmp_path) -> None:
    _seed_repo(tmp_path, monkeypatch)

    result = runner.invoke(app, ["runtime", "list"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "vllm" in result.stdout


@patch("llm_cli.commands.runtime_cmd.run_runtime_bash", return_value=0)
def test_runtime_install_vllm_mocks_bash_pip(mock_run_runtime_bash, monkeypatch, tmp_path) -> None:
    _seed_repo(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["runtime", "install", "vllm", "--yes"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "vllm")
    assert rec is not None
    assert rec.build_params == {}
    assert mock_run_runtime_bash.call_count == 2
    scripts = [call.args[2] for call in mock_run_runtime_bash.call_args_list]
    assert scripts == ["build.sh", "verify.sh"]
    build_env = mock_run_runtime_bash.call_args_list[0].kwargs["extra_env"]
    assert "LLM_BUILD_VLLM_VERSION" not in build_env
    assert "LLM_BUILD_PIP_EXTRA" not in build_env
    assert "LLM_BUILD_EXTRA_PIP_PACKAGES" not in build_env
    assert "LLM_BUILD_FORCE_REINSTALL" not in build_env


def test_config_new_vllm_injects_model_path(monkeypatch, tmp_path) -> None:
    repo = _seed_repo(tmp_path, monkeypatch)
    _seed_model_registry(monkeypatch)

    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "vllm",
            "--model",
            "qwen-sf",
            "--preset",
            "default",
            "--param",
            "dtype=bfloat16",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    out_path = tmp_path / "data" / "user" / "configs" / "vllm__qwen-sf__default.yaml"
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "runtime: vllm" in text
    assert "model: qwen-sf" in text
    assert "model: ${model_path}" in text
