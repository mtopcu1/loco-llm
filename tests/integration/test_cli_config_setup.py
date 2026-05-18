"""End-to-end tests for `llm config setup` wizard."""
from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from llm_cli.main import app

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


def test_config_setup_writes_valid_yaml(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)

    from llm_cli.core import wizards

    answers = iter(
        [
            "${model_path}",
            "-1",
            "8192",
            "127.0.0.1",
            "8080",
            "default",
        ]
    )
    monkeypatch.setattr(
        wizards,
        "text",
        lambda prompt, **k: next(answers, k.get("default", "")),
    )
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)
    monkeypatch.setattr(wizards, "review", lambda rows, **k: "save")

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
    out_path = repo / "configs" / "llamacpp__qwen-7b__default.yaml"
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "gguf_path: ${model_path}" in text


def test_config_setup_abort_writes_nothing(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    from llm_cli.core import wizards

    answers = iter(
        [
            "${model_path}",
            "-1",
            "8192",
            "127.0.0.1",
            "8080",
            "default",
        ]
    )
    monkeypatch.setattr(
        wizards,
        "text",
        lambda prompt, **k: next(answers, k.get("default", "")),
    )
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)
    monkeypatch.setattr(wizards, "review", lambda rows, **k: "abort")

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
    assert not (repo / "configs" / "llamacpp__qwen-7b__default.yaml").exists()


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
        assert "llm model pull" in result.output
    finally:
        wizards.force_plain(False)
