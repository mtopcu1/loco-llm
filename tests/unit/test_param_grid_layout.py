"""Unit tests for param grid terminal layout helpers."""

from __future__ import annotations

from llm_cli.core.param_grid_layout import (
    format_row_triple,
    format_row_pair,
    key_column_width,
    scroll_offset_for_focus,
    truncate,
    wrap_lines,
)


def test_key_column_width_respects_terminal() -> None:
    assert key_column_width(["short", "much-longer-key"], 40) >= 8
    assert key_column_width(["short", "much-longer-key"], 40) <= 20


def test_truncate_ellipsis() -> None:
    assert truncate("hello world", 8) == "hello w\u2026"


def test_format_row_triple_includes_description() -> None:
    key, val, desc = format_row_triple(
        "ctx",
        "8192",
        "Context size in tokens",
        key_width=10,
        val_width=8,
        total_width=60,
    )
    assert "ctx" in key
    assert "8192" in val
    assert "Context" in desc


def test_format_row_pair_aligns() -> None:
    key, val = format_row_pair("ctx", "8192", key_width=10, total_width=30)
    assert len(key) <= 10
    assert val


def test_wrap_lines() -> None:
    lines = wrap_lines("one two three four five", 10)
    assert len(lines) >= 2


def test_scroll_offset_keeps_focus_visible() -> None:
    off = scroll_offset_for_focus(10, total_rows=20, viewport_rows=5, current_offset=0)
    assert off == 6
