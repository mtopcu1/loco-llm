"""Unit tests for `llm setup` Y/n chain orchestrator."""
from __future__ import annotations

from pathlib import Path

import typer

from llm_cli.core import chain


def test_chain_skip_all_steps_returns_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "")
    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))
    assert chain.run_setup_chain() == 0


def test_chain_runtime_setup_failure_aborts(monkeypatch, tmp_path):
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "")
    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))

    def boom():
        raise typer.Exit(1)

    monkeypatch.setattr(chain, "_do_runtime_setup", boom)
    assert chain.run_setup_chain() != 0


def test_chain_threads_ids_forward(monkeypatch, tmp_path):
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
    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))

    assert chain.run_setup_chain() == 0
    assert calls[0]["runtime_id"] == "rt-x"
    assert calls[0]["model_id"] == "model-x"
    assert calls[1]["serve_id"] == "cfg-x"


def test_chain_duplicate_model_keep(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

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

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))

    assert chain.run_setup_chain() == 0


def test_chain_duplicate_model_force(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

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

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))

    assert chain.run_setup_chain() == 0
    assert len(calls) == 2
    assert calls[1].get("force") is True


def test_chain_duplicate_model_skip(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError

    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf.co/x")

    def pull(url, **kw):
        raise DuplicateModelRegistrationError("dup")

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "skip")

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))

    assert chain.run_setup_chain() == 0


def test_chain_duplicate_model_rename(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError
    from llm_cli.core import wizards as wiz_mod
    from llm_cli.core.settings import save_settings

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    save_settings(
        {"data_root": str(tmp_path / "data"), "repo_root": str(tmp_path)}
    )
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

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    assert chain.run_setup_chain() == 0


def test_chain_duplicate_force_pull_error_aborts(monkeypatch, tmp_path):
    from llm_cli.commands.model_cmd import DuplicateModelRegistrationError, PullModelError

    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf.co/x")

    def pull(url, **kw):
        if kw.get("force"):
            raise PullModelError("simulated hf failure")
        raise DuplicateModelRegistrationError("dup-id")

    monkeypatch.setattr(chain, "_do_model_pull", pull)
    monkeypatch.setattr(chain, "_duplicate_model_menu", lambda existing_id: "force")

    from llm_cli.core import repo as repo_mod

    monkeypatch.setattr(repo_mod, "repo_root", lambda: Path(tmp_path))

    assert chain.run_setup_chain() == 1
