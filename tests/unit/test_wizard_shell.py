"""Unit tests for wizard shell focus ladder."""

from __future__ import annotations

from llm_cli.core.wizard_shell import ShellFocus, move_content_down, move_content_up


def test_move_content_down_to_footer_on_last_row() -> None:
    focus = ShellFocus(content_index=2)
    moved = move_content_down(focus, total=3)
    assert moved is True
    assert focus.zone == "footer"


def test_move_content_up_from_footer() -> None:
    focus = ShellFocus(zone="footer", content_index=2)
    move_content_up(focus)
    assert focus.zone == "content"


def test_footer_next_label() -> None:
    from llm_cli.core.wizard_shell import footer_next_label

    assert footer_next_label(phase="meta", has_meta=True) == "Next"
    assert footer_next_label(phase="list", has_meta=True) == "Save"
    assert footer_next_label(phase="list", has_meta=False) == "Save"
    assert footer_next_label(phase="detail", has_meta=True) == "Next"
