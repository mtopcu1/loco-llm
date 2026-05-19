"""Unit tests for prompt-toolkit param grid helpers and dispatch."""

from __future__ import annotations

from llm_cli.core.param_grid import (
    clamp_focus_index,
    move_focus_linear,
    move_grid_focus,
    page_index_for_focus,
    run_param_grid,
)
from llm_cli.core.param_grid_layout import cell_indicator
from llm_cli.core.param_grid_models import ParamCell, ParamGridResult
from llm_cli.core.params import ParamSpec, ParamType


def test_page_index_for_focus() -> None:
    assert page_index_for_focus(0) == 0
    assert page_index_for_focus(5) == 0
    assert page_index_for_focus(6) == 1
    assert page_index_for_focus(12) == 2


def test_clamp_focus_index() -> None:
    assert clamp_focus_index(-1, total=3) == 0
    assert clamp_focus_index(1, total=3) == 1
    assert clamp_focus_index(10, total=3) == 2
    assert clamp_focus_index(0, total=0) == 0


def test_move_focus_linear_wraparound() -> None:
    assert move_focus_linear(0, total=3, delta=1) == 1
    assert move_focus_linear(2, total=3, delta=1) == 0
    assert move_focus_linear(0, total=3, delta=-1) == 2
    assert move_focus_linear(7, total=0, delta=2) == 0


def test_move_grid_focus_respects_edges() -> None:
    # 2 columns, 3 rows max. local indices: 0 1 / 2 3 / 4
    assert move_grid_focus(0, direction="left", page_len=5) == 0
    assert move_grid_focus(0, direction="right", page_len=5) == 1
    assert move_grid_focus(1, direction="down", page_len=5) == 3
    # Down from slot 3 would point to slot 5, which does not exist.
    assert move_grid_focus(3, direction="down", page_len=5) == 3
    # Right from slot 4 would point to a missing slot on last row.
    assert move_grid_focus(4, direction="right", page_len=5) == 4


def test_run_param_grid_uses_plain_when_requested(monkeypatch) -> None:
    expected = ParamGridResult(values={}, meta={}, action="abort")
    monkeypatch.setattr("llm_cli.core.param_grid.wizards.use_plain_prompts", lambda: True)
    monkeypatch.setattr(
        "llm_cli.core.param_grid.run_param_grid_plain",
        lambda cells, meta, *, specs, title, theme: expected,
    )

    got = run_param_grid([], [], specs=[], title="T")
    assert got is expected


def test_run_param_grid_tui_builds_keybindings(monkeypatch) -> None:
    """Regression: invalid kb.add('any') crashed before Application.run()."""
    cells = [
        ParamCell(
            key="ctx",
            label="ctx",
            description="Context",
            value="8192",
            enabled=True,
            param_type=ParamType.INT,
        )
    ]
    specs = [ParamSpec("ctx", ParamType.INT)]
    expected = ParamGridResult(
        values={"ctx": "8192"},
        meta={},
        action="abort",
        advanced_revealed=False,
    )
    monkeypatch.setattr("llm_cli.core.param_grid.wizards.use_plain_prompts", lambda: False)

    class FakeApp:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self):
            return expected

    import prompt_toolkit.application as app_mod

    monkeypatch.setattr(app_mod, "Application", FakeApp)
    got = run_param_grid(cells, [], specs=specs, title="Test")
    assert got is expected


def test_toggle_enable_clears_value_when_disabled() -> None:
    cell = ParamCell(
        key="ctx",
        label="ctx",
        description="",
        value="8192",
        enabled=True,
        param_type=ParamType.INT,
    )
    cell.enabled = False
    cell.value = ""
    assert cell.enabled is False
    assert cell.value == ""
    assert cell_indicator(cell) == "[ ]"


def test_toggle_enable_shows_enabled_indicator() -> None:
    cell = ParamCell(
        key="flag",
        label="flag",
        description="",
        value="false",
        enabled=True,
        param_type=ParamType.BOOL,
    )
    assert cell_indicator(cell) == "[x]"


def test_run_param_grid_keyboard_interrupt_returns_abort(monkeypatch) -> None:
    monkeypatch.setattr("llm_cli.core.param_grid.wizards.use_plain_prompts", lambda: False)

    def _raise(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("llm_cli.core.param_grid._run_param_grid_tui", _raise)
    got = run_param_grid([], [], specs=[], title="T")
    assert got.action == "abort"


def test_run_param_grid_falls_back_on_import_error(monkeypatch) -> None:
    expected = ParamGridResult(values={"x": "1"}, meta={}, action="save")
    monkeypatch.setattr("llm_cli.core.param_grid.wizards.use_plain_prompts", lambda: False)

    def _boom(*_args, **_kwargs):
        raise ImportError("missing prompt_toolkit")

    monkeypatch.setattr("llm_cli.core.param_grid._run_param_grid_tui", _boom)
    monkeypatch.setattr(
        "llm_cli.core.param_grid.run_param_grid_plain",
        lambda cells, meta, *, specs, title, theme: expected,
    )
    got = run_param_grid([], [], specs=[], title="T")
    assert got is expected
