"""Unit tests for Rich fallback param grid (mocked console + prompts)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from llm_cli.core.param_grid_models import MetaField, ParamCell
from llm_cli.core.param_grid_plain import run_param_grid_plain
from llm_cli.core.params import ParamType


def _cells_mixed() -> list[ParamCell]:
    return [
        ParamCell(
            key="port",
            label="Port",
            description="Listen port",
            value="8000",
            default="8000",
            tier="common",
            param_type=ParamType.INT,
        ),
        ParamCell(
            key="extra",
            label="Extra",
            description="Advanced knob",
            value="off",
            default="on",
            tier="advanced",
            param_type=ParamType.STRING,
        ),
    ]


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_save_returns_values_and_meta(mock_ask: MagicMock) -> None:
    console = MagicMock()
    mock_ask.side_effect = ["N", "S"]
    meta = [MetaField("host", "Host", "127.0.0.1", "bind")]
    cells = _cells_mixed()
    r = run_param_grid_plain(
        cells,
        meta,
        title="Test",
        console=console,
    )
    assert r.action == "save"
    assert r.values["port"] == "8000"
    assert r.meta == {"host": "127.0.0.1"}
    assert r.advanced_revealed is False
    console.print.assert_called()
    assert mock_ask.call_count == 2


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_abort(mock_ask: MagicMock) -> None:
    mock_ask.side_effect = ["x"]
    r = run_param_grid_plain(_cells_mixed(), [], title="T", console=MagicMock())
    assert r.action == "abort"


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_toggle_advanced_shows_extra_row(mock_ask: MagicMock) -> None:
    console = MagicMock()
    mock_ask.side_effect = ["A", "S"]
    r = run_param_grid_plain(_cells_mixed(), [], title="T", console=console)
    assert r.advanced_revealed is True

    tables = [
        c.args[0]
        for c in console.print.call_args_list
        if c.args and type(c.args[0]).__name__ == "Table"
    ]
    assert len(tables) == 2
    assert len(tables[0].rows) == 1
    assert len(tables[1].rows) == 2


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_edit_coerces_int(mock_ask: MagicMock) -> None:
    cells = _cells_mixed()
    mock_ask.side_effect = ["1", "9001", "S"]
    r = run_param_grid_plain(cells, [], title="T", console=MagicMock())
    assert r.action == "save"
    assert r.values["port"] == "9001"


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_edit_readonly_hidden_from_list(mock_ask: MagicMock) -> None:
    cells = [
        ParamCell(
            key="ro",
            label="RO",
            description="",
            value="fixed",
            default="fixed",
            readonly=True,
            tier="common",
            param_type=ParamType.STRING,
        ),
        ParamCell(
            key="port",
            label="Port",
            description="Listen port",
            value="8000",
            default="8000",
            tier="common",
            param_type=ParamType.INT,
        ),
    ]
    console = MagicMock()
    mock_ask.side_effect = ["S"]
    r = run_param_grid_plain(cells, [], title="T", console=console)
    assert r.action == "save"
    tables = [
        c.args[0]
        for c in console.print.call_args_list
        if c.args and type(c.args[0]).__name__ == "Table"
    ]
    assert len(tables[0].rows) == 1
    assert r.values["ro"] == "fixed"


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_edit_invalid_int_shows_error(mock_ask: MagicMock) -> None:
    cells = _cells_mixed()
    mock_ask.side_effect = ["1", "not-an-int", "S"]
    r = run_param_grid_plain(cells, [], title="T", console=MagicMock())
    assert r.action == "save"
    assert r.values["port"] == "8000"


@patch("llm_cli.core.param_grid_plain.Prompt.ask")
def test_unknown_command_then_save(mock_ask: MagicMock) -> None:
    mock_ask.side_effect = ["q", "S"]
    r = run_param_grid_plain(_cells_mixed(), [], title="T", console=MagicMock())
    assert r.action == "save"
    assert mock_ask.call_count == 2
