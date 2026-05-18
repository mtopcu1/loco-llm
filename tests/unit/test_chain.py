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
