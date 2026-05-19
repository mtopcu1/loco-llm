"""End-to-end tests for `llm config new` (non-interactive)."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from llm_cli.main import app
from tests.cli_helpers import cli_plain

runner = CliRunner()


def _seed_repo(tmp_path: Path, monkeypatch) -> Path:
    from llm_cli.core import repo as repo_mod
    from llm_cli.core import model_registry as mr
    from llm_cli.core.settings import save_settings

    workspace_root = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    shutil.copytree(workspace_root / "runtimes", tmp_path / "runtimes")
    (tmp_path / "configs").mkdir()
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)
    save_settings(
        {"data_root": str(tmp_path / "data"), "repo_root": str(tmp_path)}
    )

    fake_entry = mr.RegistryEntry(
        id="qwen-7b",
        format="gguf",
        source=mr.HFSource(repo="r"),
        artifact=mr.Artifact(
            primary="m.gguf",
            files=("m.gguf",),
            total_size_bytes=8 * 1024**3,
        ),
        metadata=mr.Metadata(),
        installed_at="",
    )

    def fake_get(models_dir, eid):
        return fake_entry if eid == "qwen-7b" else None

    reg = {"qwen-7b": fake_entry}
    monkeypatch.setattr(mr, "get_entry", fake_get)
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: reg)
    from llm_cli.commands import config_cmd as cc

    monkeypatch.setattr(cc, "get_entry", fake_get)
    monkeypatch.setattr(cc, "load_registry", lambda models_dir: reg)
    return tmp_path


def _user_config_path(tmp_path: Path, name: str) -> Path:
    return tmp_path / "data" / "user" / "configs" / name


def test_config_new_writes_valid_yaml(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
            "--preset",
            "default",
            "--param",
            "gguf_path=${model_path}",
            "--param",
            "n_gpu_layers=-1",
            "--param",
            "ctx=8192",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "runtime: llamacpp" in text
    assert "model: qwen-7b" in text
    assert "gguf_path: ${model_path}" in text


def test_config_new_saves_only_explicit_params(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
            "--preset",
            "default",
            "--param",
            "ctx=8192",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")
    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    params = doc["serve"]["params"]
    assert params == {"gguf_path": "${model_path}", "ctx": 8192}
    assert "n_gpu_layers" not in params


def test_config_new_injects_model_path_without_gguf_param(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
            "--preset",
            "default",
            "--param",
            "n_gpu_layers=-1",
            "--param",
            "ctx=8192",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "gguf_path: ${model_path}" in text


def test_config_new_requires_runtime(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(app, ["config", "new"])
    assert result.exit_code != 0
    plain = cli_plain(result).lower()
    assert "--runtime" in plain or "runtime" in plain


def test_config_new_rejects_model_for_no_model_runtime(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "stub-runtime",
            "--model",
            "qwen-7b",
        ],
    )
    assert result.exit_code != 0
    assert "stub-runtime" in result.output
    assert "model" in result.output.lower()


def test_config_new_requires_model_for_model_runtime(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(app, ["config", "new", "--runtime", "llamacpp"])
    assert result.exit_code != 0
    plain = cli_plain(result).lower()
    assert "--model" in plain or "pass --model" in plain or "model" in plain


def test_config_new_errors_on_invalid_param(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
            "--param",
            "n_gpu_layers=not_an_int",
        ],
    )
    assert result.exit_code != 0
    assert "n_gpu_layers" in result.output


def test_config_new_overwrite_requires_force(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    ( _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")).parent.mkdir(
        parents=True, exist_ok=True
    )
    ( _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")).write_text(
        "id: llamacpp__qwen-7b__default\nruntime: llamacpp\nmodel: qwen-7b\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
            "--param",
            "gguf_path=${model_path}",
        ],
    )
    assert result.exit_code != 0
    assert "exists" in result.output.lower()

    result2 = runner.invoke(
        app,
        [
            "config",
            "new",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
            "--param",
            "gguf_path=${model_path}",
            "--force",
        ],
    )
    assert result2.exit_code == 0, result2.output
