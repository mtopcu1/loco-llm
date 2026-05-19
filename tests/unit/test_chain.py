"""Unit tests for `llm setup` Y/n chain orchestrator."""
from __future__ import annotations

from pathlib import Path

import typer

from llm_cli.core import chain


def _chain_settings(tmp_path: Path, monkeypatch) -> None:
    from llm_cli.core.settings import save_settings

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(tmp_path)})


def test_chain_skip_all_steps_returns_zero(monkeypatch, tmp_path):
    _chain_settings(tmp_path, monkeypatch)
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "")
    assert chain.run_setup_chain() == 0


def test_chain_runtime_setup_failure_aborts(monkeypatch, tmp_path):
    _chain_settings(tmp_path, monkeypatch)
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "")

    def boom():
        raise typer.Exit(1)

    monkeypatch.setattr(chain, "_do_runtime_setup", boom)
    assert chain.run_setup_chain() != 0


def test_chain_threads_ids_forward(monkeypatch, tmp_path):
    _chain_settings(tmp_path, monkeypatch)
    calls: list[object] = []

    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(
        chain,
        "_prompt_text",
        lambda *a, **k: "https://huggingface.co/x",
    )
    monkeypatch.setattr(chain, "_do_runtime_setup", lambda: "rt-x")
    monkeypatch.setattr(chain, "_do_model_pull", lambda url: "model-x")

    def fake_config(**kwargs):
        calls.append(kwargs)
        return "cfg-x"

    def fake_serve(cid):
        calls.append({"serve_id": cid})
        return 0

    monkeypatch.setattr(chain, "_do_config_setup", fake_config)
    monkeypatch.setattr(chain, "_do_serve", fake_serve)

    assert chain.run_setup_chain() == 0
    assert calls[0]["runtime_id"] == "rt-x"
    assert calls[0]["model_id"] == "model-x"
    assert calls[1]["serve_id"] == "cfg-x"


def test_chain_duplicate_model_keep(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

    _chain_settings(tmp_path, monkeypatch)
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(
        chain,
        "_prompt_text",
        lambda *a, **k: "https://huggingface.co/org/repo/blob/main/x.gguf",
    )

    def pull(url, **kw):
        raise DuplicateModelRegistrationError("dup-id")

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "keep")

    assert chain.run_setup_chain() == 0


def test_chain_duplicate_model_force(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

    _chain_settings(tmp_path, monkeypatch)
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf.co/x/y/blob/main/z.gguf")

    calls: list[dict] = []

    def pull(url, **kw):
        calls.append(dict(kw))
        if not kw.get("force"):
            raise DuplicateModelRegistrationError("dup-id")
        return "dup-id"

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "force")

    assert chain.run_setup_chain() == 0
    assert len(calls) == 2
    assert calls[1].get("force") is True


def test_chain_duplicate_model_skip(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

    _chain_settings(tmp_path, monkeypatch)
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf.co/x")

    def pull(url, **kw):
        raise DuplicateModelRegistrationError("dup")

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "skip")

    assert chain.run_setup_chain() == 0


def test_chain_duplicate_model_rename(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError
    from llm_cli.core import wizards as wiz_mod

    _chain_settings(tmp_path, monkeypatch)
    (tmp_path / "data" / "models").mkdir(parents=True)

    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf.co/x")

    def pull(url, **kw):
        if kw.get("id_override") == "my-alt":
            return "my-alt"
        raise DuplicateModelRegistrationError("dup-id")

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "rename")

    monkeypatch.setattr(
        wiz_mod,
        "text",
        lambda prompt, validate=None, default=None, **k: "my-alt",
    )

    assert chain.run_setup_chain() == 0


def test_chain_duplicate_force_pull_error_aborts(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError, PullModelError

    _chain_settings(tmp_path, monkeypatch)
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf.co/x")

    def pull(url, **kw):
        if kw.get("force"):
            raise PullModelError("simulated hf failure")
        raise DuplicateModelRegistrationError("dup-id")

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "force")

    assert chain.run_setup_chain() == 1
