"""PTY integration tests for `loco runtime setup` wizard."""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("pexpect")

from llm_cli.core.install_record import read_record

from tests.tui import keys as k
from tests.tui.session import TuiSession

pytestmark = [
    pytest.mark.tui,
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="pexpect TUI tests require Unix PTY",
    ),
]


def _pick_preset_branch(session: TuiSession) -> None:
    session.expect("Runtime setup", timeout=20)
    session.send(k.ENTER)


def _pick_stub_runtime(session: TuiSession) -> None:
    session.expect("Pick a preset", timeout=20)
    # Official presets sort as llamacpp, stub-runtime, vllm.
    session.send(k.DOWN)
    session.send(k.ENTER)


def test_tui_runtime_setup_preset_installs_stub(tui_repo) -> None:
    fixture = tui_repo
    session = TuiSession.spawn(fixture, ["runtime", "setup"])
    try:
        _pick_preset_branch(session)
        _pick_stub_runtime(session)
        session.expect("stub-runtime", timeout=30)
        assert session.wait_exit(timeout=120) == 0
    finally:
        session.close()

    record = read_record(fixture.runtimes_dir, "stub-runtime")
    assert record is not None
    assert record.runtime_id == "stub-runtime"


@pytest.mark.skip(reason="questionary cancel keys are not delivered reliably in pexpect PTY")
def test_tui_runtime_setup_abort_on_branch(tui_repo) -> None:
    fixture = tui_repo
    session = TuiSession.spawn(fixture, ["runtime", "setup"])
    try:
        session.expect("Runtime setup", timeout=20)
        session.send(k.ESC)
        session.expect("aborted", timeout=20)
        assert session.wait_exit() != 0
    finally:
        session.close()

    assert read_record(fixture.runtimes_dir, "stub-runtime") is None


def test_tui_runtime_setup_custom_refuses_existing_id(tui_repo) -> None:
    fixture = tui_repo
    session = TuiSession.spawn(fixture, ["runtime", "setup"])
    try:
        session.expect("Runtime setup", timeout=20)
        session.send(k.DOWN)
        session.send(k.ENTER)
        session.expect("Runtime id", timeout=20)
        session.send("llamacpp")
        session.send(k.ENTER)
        session.expect("already exists", timeout=20)
        assert session.wait_exit() != 0
    finally:
        session.close()


def test_tui_runtime_setup_custom_template_minimal(tui_repo) -> None:
    fixture = tui_repo
    session = TuiSession.spawn(fixture, ["runtime", "setup"])
    try:
        session.expect("Runtime setup", timeout=20)
        session.send(k.DOWN)
        session.send(k.ENTER)
        session.expect("Runtime id", timeout=20)
        session.send("tui-custom")
        session.send(k.ENTER)
        session.expect("Display name", timeout=20)
        session.send(k.ENTER)
        session.expect("Accepts which model formats", timeout=20)
        # Select "none (no model needed)" — third checkbox option.
        session.send(k.DOWN)
        session.send(k.DOWN)
        session.send(k.SPACE)
        session.send(k.ENTER)
        session.expect("Serve command", timeout=20)
        session.send(k.ENTER)
        session.expect("Bare invocation", timeout=20)
        session.send(k.ENTER)
        session.expect("requires", timeout=20)
        session.send(k.ENTER)
        session.expect("tui-custom", timeout=30)
        assert session.wait_exit(timeout=60) == 0
    finally:
        session.close()

    rt_dir = fixture.user_runtimes_dir / "tui-custom"
    assert (rt_dir / "manifest.yaml").is_file()
    assert (rt_dir / "serve.sh").is_file()
    manifest = (rt_dir / "manifest.yaml").read_text(encoding="utf-8")
    assert "kind: custom" in manifest

    record = read_record(fixture.runtimes_dir, "tui-custom")
    assert record is not None
