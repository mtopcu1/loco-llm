"""PTY integration tests for `llm runtime install` opt-in param grid."""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("pexpect")

from llm_cli.core.install_record import read_record

from tests.tui import keys as k
from tests.tui import workflows as wf
from tests.tui.seed import add_tiered_build_runtime
from tests.tui.session import TuiSession

pytestmark = [
    pytest.mark.tui,
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="pexpect TUI tests require Unix PTY",
    ),
]


def _save_build_params_footer(session: TuiSession, *, visible_rows: int) -> None:
    session.expect("Parameters", timeout=20)
    for _ in range(max(0, visible_rows - 1)):
        session.send(k.DOWN)
    session.send(k.DOWN)
    session.send(k.RIGHT)
    session.send(k.ENTER)


def _enable_param_and_set(session: TuiSession, value: str) -> None:
    """Enable focused optional param (Space), open detail, set value, commit."""
    session.send(k.SPACE)
    session.send(k.ENTER)
    session.send(value)
    session.send(k.ENTER)


def test_tui_runtime_install_common_only_saves_opted_in_build_params(tui_repo) -> None:
    fixture = tui_repo
    add_tiered_build_runtime(fixture.repo_root)
    session = TuiSession.spawn(fixture, ["runtime", "install", "tier-rt"])
    try:
        # Opt in to common-tier flavor only (advanced extra_jobs stays disabled).
        session.expect("Parameters", timeout=20)
        _enable_param_and_set(session, "cpu")
        _save_build_params_footer(session, visible_rows=1)
        assert session.wait_exit(timeout=60) == 0
    finally:
        session.close()

    rec = read_record(fixture.runtimes_dir, "tier-rt")
    assert rec is not None
    assert rec.build_params == {"flavor": "cpu"}


def test_tui_runtime_install_abort_from_param_grid(tui_repo) -> None:
    fixture = tui_repo
    add_tiered_build_runtime(fixture.repo_root)
    session = TuiSession.spawn(fixture, ["runtime", "install", "tier-rt"])
    try:
        session.expect("Parameters", timeout=20)
        wf.abort_params_only(session)
        assert session.wait_exit(timeout=60) != 0
    finally:
        session.close()

    rec = read_record(fixture.runtimes_dir, "tier-rt")
    assert rec is None
