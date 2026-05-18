"""End-to-end tests for `llm runtime setup`."""
from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _seed(tmp_path: Path, monkeypatch) -> Path:
    from llm_cli.core import repo as repo_mod
    from llm_cli.core.settings import save_settings

    workspace_root = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    shutil.copytree(workspace_root / "runtimes", tmp_path / "runtimes")
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)
    save_settings(
        {"data_root": str(tmp_path / "data"), "repo_root": str(tmp_path)}
    )
    return tmp_path


def test_runtime_setup_preset_lists_official_runtimes(monkeypatch, tmp_path):
    _seed(tmp_path, monkeypatch)
    from llm_cli.core import wizards

    picks = iter(
        [
            "Preset — install an official runtime",
            "stub-runtime",
        ]
    )
    monkeypatch.setattr(wizards, "select", lambda prompt, choices, **k: next(picks))

    from llm_cli.commands import runtime_cmd

    monkeypatch.setattr(runtime_cmd, "_run_install_for_id", lambda *a, **k: None)

    result = runner.invoke(app, ["runtime", "setup"])
    assert result.exit_code == 0, result.output
    assert "stub-runtime" in result.output


def test_runtime_setup_custom_writes_all_files(monkeypatch, tmp_path):
    repo = _seed(tmp_path, monkeypatch)

    from llm_cli.core import wizards

    text_answers = iter(
        [
            "vllm-custom",
            "vLLM (user-installed)",
            'vllm serve "$LLM_MODEL_PATH" --host "$LLM_SERVE_HOST" --port "$LLM_SERVE_PORT" $LLM_EXTRA_ARGS',
            "",
        ]
    )
    select_answers = iter(
        [
            "Custom — register an existing install",
            "Template (we wrap in bash)",
        ]
    )
    monkeypatch.setattr(
        wizards, "select", lambda prompt, choices, **k: next(select_answers)
    )
    monkeypatch.setattr(
        wizards,
        "checkbox",
        lambda prompt, choices, **k: ("safetensors-dir",),
    )
    monkeypatch.setattr(
        wizards,
        "text",
        lambda prompt, **k: next(text_answers, k.get("default", "")),
    )
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)

    from llm_cli.core import settings as settings_mod
    from llm_cli.core.settings import Settings

    new_settings = Settings(
        data_root=tmp_path / "data",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
        repo_root=tmp_path,
    )
    monkeypatch.setattr(settings_mod, "resolve", lambda *a, **k: new_settings)

    result = runner.invoke(app, ["runtime", "setup"])
    assert result.exit_code == 0, result.output

    rt_dir = repo / "runtimes" / "vllm-custom"
    assert (rt_dir / "manifest.yaml").is_file()
    assert (rt_dir / "serve.sh").is_file()
    assert (rt_dir / "healthcheck.sh").is_file()
    assert (rt_dir / "params.yaml").is_file()

    manifest = (rt_dir / "manifest.yaml").read_text(encoding="utf-8")
    assert "kind: custom" in manifest
    assert "safetensors-dir" in manifest

    params = (rt_dir / "params.yaml").read_text(encoding="utf-8")
    assert "extra_args" in params

    installed = new_settings.runtimes_dir / "vllm-custom" / ".installed"
    assert installed.is_file()


def test_runtime_setup_custom_refuses_existing_id(monkeypatch, tmp_path):
    repo = _seed(tmp_path, monkeypatch)

    from llm_cli.core import wizards

    select_answers = iter(
        [
            "Custom — register an existing install",
            "Template (we wrap in bash)",
        ]
    )
    text_answers = iter(["llamacpp"])
    monkeypatch.setattr(
        wizards, "select", lambda prompt, choices, **k: next(select_answers)
    )
    monkeypatch.setattr(
        wizards,
        "text",
        lambda prompt, **k: next(text_answers, k.get("default", "")),
    )
    monkeypatch.setattr(
        wizards,
        "checkbox",
        lambda prompt, choices, **k: ("gguf",),
    )
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)

    result = runner.invoke(app, ["runtime", "setup"])
    assert result.exit_code != 0
    assert "already exists" in result.output.lower()


def test_runtime_install_refuses_custom_kind(monkeypatch, tmp_path):
    repo = _seed(tmp_path, monkeypatch)
    (repo / "runtimes" / "fake-custom").mkdir(parents=True)
    (repo / "runtimes" / "fake-custom" / "manifest.yaml").write_text(
        "id: fake-custom\ndisplay_name: Fake\nkind: custom\naccepts_formats: []\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["runtime", "install", "fake-custom"])
    assert result.exit_code != 0
    assert "custom" in result.output.lower()
    out = result.output.replace("\n", " ")
    assert "runtime setup" in out.lower()


def test_runtime_rebuild_refuses_custom_kind(monkeypatch, tmp_path):
    repo = _seed(tmp_path, monkeypatch)
    (repo / "runtimes" / "fake-custom").mkdir(parents=True)
    (repo / "runtimes" / "fake-custom" / "manifest.yaml").write_text(
        "id: fake-custom\ndisplay_name: Fake\nkind: custom\naccepts_formats: []\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["runtime", "rebuild", "fake-custom"])
    assert result.exit_code != 0
    assert "rebuild applies to official" in result.output.lower()
