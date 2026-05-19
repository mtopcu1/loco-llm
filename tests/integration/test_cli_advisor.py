"""End-to-end tests for `llm advisor`."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from llm_cli.main import app
from tests.cli_helpers import cli_plain

runner = CliRunner()

_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _configure_user_settings(monkeypatch, tmp_path: Path, repo_root: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from llm_cli.core.settings import save_settings

    save_settings(
        {"data_root": str(tmp_path / "data"), "repo_root": str(repo_root)}
    )


def _patch_specs(monkeypatch):
    from llm_cli.commands import advisor as advisor_mod
    from llm_cli.core import specs as specs_mod
    from llm_cli.core.specs import CpuInfo, GpuInfo, SystemSpecs

    fake = SystemSpecs(
        cpu=CpuInfo(model="X", logical_cores=1),
        ram_gb=16,
        gpus=[GpuInfo(index=0, name="NVIDIA RTX 4090", vram_gb=24, driver="560")],
    )

    def fake_detect_all(**_kwargs):
        return fake

    # advisor imports detect_all by name; patch both module and consumer.
    monkeypatch.setattr(specs_mod, "detect_all", fake_detect_all)
    monkeypatch.setattr(advisor_mod, "detect_all", fake_detect_all)


def _patch_model(monkeypatch, model_id: str, size_bytes: int):
    from llm_cli.core.model_registry import (
        Artifact,
        HFSource,
        Metadata,
        RegistryEntry,
    )
    from llm_cli.core import model_registry as mr

    entry = RegistryEntry(
        id=model_id,
        format="gguf",
        source=HFSource(repo="r"),
        artifact=Artifact(
            primary="m.gguf",
            files=("m.gguf",),
            total_size_bytes=size_bytes,
        ),
        metadata=Metadata(),
        installed_at="",
    )

    def fake_get(models_dir, eid):
        return entry if eid == model_id else None

    monkeypatch.setattr(mr, "get_entry", fake_get)
    from llm_cli.commands import advisor as advisor_mod

    monkeypatch.setattr(advisor_mod, "_get_model", fake_get)


def _suppress_advisor_config_offer(monkeypatch) -> None:
    from llm_cli.commands import advisor as advisor_mod

    monkeypatch.setattr(advisor_mod, "_offer_create_config", lambda *a, **k: False)


def test_advisor_flag_form_prints_recommendations(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)
    _suppress_advisor_config_offer(monkeypatch)

    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b"]
    )
    assert result.exit_code == 0, result.output
    assert "llamacpp" in result.output
    assert "qwen-7b" in result.output
    assert "ctx" in result.output
    assert "n_gpu_layers" in result.output


def test_advisor_json_output(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    result = runner.invoke(
        app,
        ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["runtime"] == "llamacpp"
    assert payload["model"] == "qwen-7b"
    assert "ctx" in payload["recommendations"]
    assert "n_gpu_layers" in payload["recommendations"]
    assert payload["machine"]["gpus"][0]["vram_gb"] == 24


def test_advisor_requires_both_runtime_and_model(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    result = runner.invoke(app, ["advisor", "--runtime", "llamacpp"])
    assert result.exit_code != 0
    plain = cli_plain(result).lower()
    assert "both --runtime and --model" in plain or (
        "both" in plain and "runtime" in plain and "model" in plain
    )


def test_advisor_errors_on_unknown_model(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "exists", 8 * 1024**3)
    result = runner.invoke(
        app,
        ["advisor", "--runtime", "llamacpp", "--model", "nope"],
    )
    assert result.exit_code != 0
    assert "nope" in result.output.lower()


def test_advisor_emits_empty_recommendations_for_unsupported_runtime(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "exists", 8 * 1024**3)
    result = runner.invoke(
        app,
        ["advisor", "--runtime", "vllm", "--model", "exists"],
    )
    assert result.exit_code != 0
    assert "vllm" in result.output.lower()


def test_advisor_config_id_form(monkeypatch, tmp_path):
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    (cfg_dir / "llamacpp__qwen-7b__default.yaml").write_text(
        "id: llamacpp__qwen-7b__default\n"
        "runtime: llamacpp\n"
        "model: qwen-7b\n"
        "serve:\n"
        "  host: 127.0.0.1\n"
        "  port: 8080\n"
        "  params:\n"
        '    gguf_path: "${model_path}"\n',
        encoding="utf-8",
    )

    import shutil

    shutil.copytree(_WORKSPACE_ROOT / "runtimes", tmp_path / "runtimes")

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)
    _configure_user_settings(monkeypatch, tmp_path, tmp_path)
    _suppress_advisor_config_offer(monkeypatch)

    result = runner.invoke(app, ["advisor", "llamacpp__qwen-7b__default"])
    assert result.exit_code == 0, result.output
    assert "llamacpp" in result.output
    assert "qwen-7b" in result.output


def test_advisor_config_id_unknown_errors(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, tmp_path)
    _patch_specs(monkeypatch)
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    result = runner.invoke(app, ["advisor", "no-such-config"])
    assert result.exit_code != 0
    assert "no-such-config" in result.output


def test_advisor_rejects_positional_combined_with_flags(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    result = runner.invoke(
        app,
        ["advisor", "some-cfg", "--runtime", "llamacpp", "--model", "qwen-7b"],
    )
    assert result.exit_code != 0
    plain = cli_plain(result).lower()
    assert "either a config id or" in plain or (
        "config id" in plain and "runtime" in plain
    )


def test_advisor_interactive_picks_runtime_and_model(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, tmp_path)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    from llm_cli.core import wizards

    answers = iter(["llamacpp", "qwen-7b"])
    monkeypatch.setattr(
        wizards, "select", lambda prompt, choices, **k: next(answers)
    )

    import shutil

    shutil.copytree(_WORKSPACE_ROOT / "runtimes", tmp_path / "runtimes")

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    from llm_cli.core import model_registry as mr

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
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: {"qwen-7b": fake_entry})
    _suppress_advisor_config_offer(monkeypatch)

    result = runner.invoke(app, ["advisor"])
    assert result.exit_code == 0, result.output
    assert "llamacpp" in result.output
    assert "qwen-7b" in result.output


def test_advisor_offers_create_config_chain(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    invoked: list[dict] = []

    def fake_do_config_setup(**kwargs):
        invoked.append(kwargs)
        return "llamacpp__qwen-7b__default"

    from llm_cli.commands import config_cmd

    monkeypatch.setattr(config_cmd, "do_config_setup", fake_do_config_setup)

    from llm_cli.commands import advisor as advisor_mod

    monkeypatch.setattr(advisor_mod, "_offer_create_config", lambda *a, **k: True)

    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b"]
    )
    assert result.exit_code == 0, result.output
    assert invoked, "config setup was not invoked"
    assert invoked[0]["runtime_id"] == "llamacpp"
    assert invoked[0]["model_id"] == "qwen-7b"


def test_advisor_json_does_not_offer_chain(monkeypatch, tmp_path):
    _configure_user_settings(monkeypatch, tmp_path, _WORKSPACE_ROOT)
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)
    from llm_cli.commands import advisor as advisor_mod

    called: list[int] = []
    monkeypatch.setattr(
        advisor_mod,
        "_offer_create_config",
        lambda *a, **k: called.append(1) or True,
    )

    result = runner.invoke(
        app,
        ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b", "--json"],
    )
    assert result.exit_code == 0
    assert not called, "chain should not fire in --json mode"
