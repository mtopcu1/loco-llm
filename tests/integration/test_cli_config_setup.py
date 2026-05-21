"""End-to-end tests for `loco config setup` wizard."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from llm_cli.main import app
from tests.cli_helpers import data_config_path

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
    return data_config_path(tmp_path, name)


def test_config_setup_writes_valid_yaml(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)

    from llm_cli.core import wizards
    from llm_cli.core.param_grid_models import ParamGridResult

    def stub_edit_params(specs, **kwargs):
        return ParamGridResult(
            values={"ctx": "8192", "n_gpu_layers": "-1"},
            meta={
                "host": "127.0.0.1",
                "port": "8080",
                "preset": "default",
                "config_id": "llamacpp__qwen-7b__default",
            },
            action="save",
            advanced_revealed=False,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)

    result = runner.invoke(
        app,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "gguf_path: ${model_path}" in text
    assert "ctx: 8192" in text
    assert "n_gpu_layers: -1" in text


def test_config_setup_skips_bound_path_when_model_set(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)

    from llm_cli.core import wizards
    from llm_cli.core.param_grid_models import ParamGridResult

    captured: dict[str, object] = {}

    def stub_edit_params(specs, **kwargs):
        captured["skip_keys"] = set(kwargs.get("skip_keys", set()))
        captured["readonly_keys"] = kwargs.get("readonly_keys")
        return ParamGridResult(
            values={"ctx": "8192"},
            meta={
                "host": "127.0.0.1",
                "port": "8080",
                "preset": "default",
                "config_id": "llamacpp__qwen-7b__default",
            },
            action="save",
            advanced_revealed=False,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)

    result = runner.invoke(
        app,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gguf_path" in captured["skip_keys"]
    assert "gguf_path" in captured["readonly_keys"]
    out_path = _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")
    text_out = out_path.read_text(encoding="utf-8")
    assert "gguf_path: ${model_path}" in text_out


def test_config_setup_saves_only_enabled_params(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)

    from llm_cli.core import wizards
    from llm_cli.core.param_grid_models import ParamGridResult

    def stub_edit_params(_specs, **kwargs):
        return ParamGridResult(
            values={"ctx": "8192"},
            meta={
                "host": "127.0.0.1",
                "port": "8080",
                "preset": "default",
                "config_id": "llamacpp__qwen-7b__default",
            },
            action="save",
            advanced_revealed=False,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)

    result = runner.invoke(
        app,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml")
    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    params = doc["serve"]["params"]
    assert params == {"gguf_path": "${model_path}", "ctx": 8192}
    assert "n_gpu_layers" not in params
    assert "batch_size" not in params


def test_config_setup_abort_writes_nothing(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    from llm_cli.core import wizards
    from llm_cli.core.param_grid_models import ParamGridResult

    def stub_edit_params(_specs, **kwargs):
        return ParamGridResult(
            values={},
            meta={},
            action="abort",
            advanced_revealed=False,
        )

    monkeypatch.setattr(wizards, "edit_params", stub_edit_params)

    result = runner.invoke(
        app,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    assert result.exit_code != 0
    assert not _user_config_path(tmp_path, "llamacpp__qwen-7b__default.yaml").exists()


def test_config_setup_no_compatible_models(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    from llm_cli.core import model_registry as mr

    monkeypatch.setattr(mr, "load_registry", lambda models_dir: {})
    from llm_cli.commands import config_cmd as cc

    monkeypatch.setattr(cc, "load_registry", lambda models_dir: {})

    from llm_cli.core import wizards

    wizards.force_plain(True)
    try:
        monkeypatch.setattr(wizards, "select", lambda *a, **k: "llamacpp")
        monkeypatch.setattr(wizards, "text", lambda *a, **k: k.get("default", ""))
        monkeypatch.setattr(wizards, "confirm", lambda *a, **k: False)

        result = runner.invoke(app, ["config", "setup"])
        assert result.exit_code != 0
        assert "loco model pull" in result.output
    finally:
        wizards.force_plain(False)
