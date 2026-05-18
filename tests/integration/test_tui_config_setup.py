"""PTY integration tests for `llm config setup` param grid wizard."""
from __future__ import annotations

import sys

import yaml

import pytest

pytest.importorskip("pexpect")

from tests.tui import keys as k
from tests.tui.session import TuiSession
from tests.tui import workflows as wf

pytestmark = [
    pytest.mark.tui,
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="pexpect TUI tests require Unix PTY",
    ),
]


def test_tui_config_setup_happy_path_llamacpp(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        wf.advance_meta_to_params(session)
        wf.save_params_via_footer(
            session,
            repo_root=fixture.repo_root,
            runtime_id="llamacpp",
            model_id="qwen-7b",
        )
        assert session.wait_exit() == 0
    finally:
        session.close()

    out_path = fixture.configs_dir / "llamacpp__qwen-7b__default.yaml"
    assert out_path.is_file()
    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert doc["runtime"] == "llamacpp"
    assert doc["model"] == "qwen-7b"
    assert doc["serve"]["params"]["gguf_path"] == "${model_path}"


def test_tui_config_setup_abort_on_meta(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        session.expect("Configuration", timeout=20)
        wf.abort_wizard(session)
        assert session.wait_exit() != 0
    finally:
        session.close()

    assert not (fixture.configs_dir / "llamacpp__qwen-7b__default.yaml").exists()


def test_tui_config_setup_abort_on_params(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        wf.advance_meta_to_params(session)
        wf.abort_wizard(session, from_params=True)
        assert session.wait_exit() != 0
    finally:
        session.close()

    assert not (fixture.configs_dir / "llamacpp__qwen-7b__default.yaml").exists()


def test_tui_config_setup_back_from_params_to_meta(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        wf.advance_meta_to_params(session)
        session.send(k.ESC)
        session.expect("Configuration", timeout=20)
        wf.abort_wizard(session)
        assert session.wait_exit() != 0
    finally:
        session.close()


def test_tui_config_setup_change_port_in_meta(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        session.expect("Configuration", timeout=20)
        # host=0, port=1 — move down once and open detail editor.
        session.send(k.DOWN)
        session.send(k.ENTER)
        for _ in range(4):
            session.send("\x7f")
        session.send("9090")
        session.send(k.ENTER)
        session.send(k.RIGHT)
        wf.save_params_via_footer(
            session,
            repo_root=fixture.repo_root,
            runtime_id="llamacpp",
            model_id="qwen-7b",
        )
        assert session.wait_exit() == 0
    finally:
        session.close()

    doc = yaml.safe_load(
        (fixture.configs_dir / "llamacpp__qwen-7b__default.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert doc["serve"]["port"] == 9090


def test_tui_config_setup_invalid_port_blocks_save(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        session.expect("Configuration", timeout=20)
        session.send(k.DOWN)
        session.send(k.ENTER)
        for _ in range(4):
            session.send("\x7f")
        session.send("abc")
        session.send(k.ENTER)
        session.expect("port must be an integer", timeout=10)
        session.send(k.ESC)
        wf.abort_wizard(session)
        assert session.wait_exit() != 0
    finally:
        session.close()


def test_tui_config_setup_stub_runtime_no_model(tui_repo) -> None:
    fixture = tui_repo
    session = TuiSession.spawn(
        fixture,
        ["config", "setup", "--runtime", "stub-runtime"],
    )
    try:
        wf.advance_meta_to_params(session)
        wf.save_empty_params(session)
        assert session.wait_exit() == 0
    finally:
        session.close()

    out_path = fixture.configs_dir / "stub-runtime__default.yaml"
    assert out_path.is_file()
    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert doc["runtime"] == "stub-runtime"
    assert "model" not in doc


def test_tui_config_setup_no_compatible_models(tui_repo) -> None:
    fixture = tui_repo
    session = TuiSession.spawn(
        fixture,
        ["config", "setup", "--runtime", "llamacpp"],
    )
    try:
        session.expect("no compatible models", timeout=20)
        assert session.wait_exit() != 0
    finally:
        session.close()


def test_tui_config_setup_rejects_model_on_stub_runtime(tui_repo_with_model) -> None:
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "stub-runtime",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        session.expect("does not use models", timeout=20)
        assert session.wait_exit() != 0
    finally:
        session.close()


def test_tui_config_setup_gguf_path_hidden_in_list(tui_repo_with_model) -> None:
    """Bound gguf_path is saved but not shown as an editable list row."""
    fixture = tui_repo_with_model
    session = TuiSession.spawn(
        fixture,
        [
            "config",
            "setup",
            "--runtime",
            "llamacpp",
            "--model",
            "qwen-7b",
        ],
    )
    try:
        wf.advance_meta_to_params(session)
        session.expect("Parameters", timeout=20)
        buf = session.buffer
        assert "gguf_path" not in buf
        wf.save_params_via_footer(
            session,
            repo_root=fixture.repo_root,
            runtime_id="llamacpp",
            model_id="qwen-7b",
            expect_params=False,
        )
        assert session.wait_exit() == 0
    finally:
        session.close()

    text = (fixture.configs_dir / "llamacpp__qwen-7b__default.yaml").read_text(
        encoding="utf-8"
    )
    assert "gguf_path: ${model_path}" in text
