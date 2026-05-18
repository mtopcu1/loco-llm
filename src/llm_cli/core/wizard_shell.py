"""Shared wizard footer and focus ladder for TUI masks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.formatted_text import StyleAndTextTuples

FocusZone = Literal["content", "footer"]
FooterButton = Literal["back", "next"]


@dataclass
class ShellFocus:
    zone: FocusZone = "content"
    content_index: int = 0
    footer_button: FooterButton = "back"
    scroll_offset: int = 0


def clamp_content_index(index: int, *, total: int) -> int:
    if total <= 0:
        return 0
    if index < 0:
        return 0
    if index >= total:
        return total - 1
    return index


def move_content(focus: ShellFocus, delta: int, *, total: int) -> None:
    if total <= 0:
        focus.content_index = 0
        return
    focus.content_index = (focus.content_index + delta) % total


def move_content_down(focus: ShellFocus, *, total: int) -> bool:
    """Move down in content. Returns True if focus moved to footer."""
    if total <= 0:
        focus.zone = "footer"
        focus.footer_button = "back"
        return True
    if focus.content_index >= total - 1:
        focus.zone = "footer"
        focus.footer_button = "back"
        return True
    focus.content_index += 1
    return False


def move_content_up(focus: ShellFocus) -> None:
    if focus.zone == "footer":
        focus.zone = "content"
        return
    if focus.content_index > 0:
        focus.content_index -= 1


def toggle_footer_button(focus: ShellFocus) -> None:
    focus.footer_button = "next" if focus.footer_button == "back" else "back"


def render_footer(
    *,
    back_label: str = "Back",
    next_label: str = "Next",
    focused_button: FooterButton,
    in_footer: bool,
) -> StyleAndTextTuples:
    """Render ``Back  Next`` left-aligned with list rows (after focus marker column)."""
    back_cls = "class:cell-focus" if in_footer and focused_button == "back" else "class:text-dim"
    next_cls = "class:cell-focus" if in_footer and focused_button == "next" else "class:text-dim"
    return [
        ("class:text-dim", " "),
        (back_cls, back_label),
        ("class:text-dim", "  "),
        (next_cls, next_label),
    ]
