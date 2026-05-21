"""Focus navigation helpers for the param grid TUI."""
from __future__ import annotations

from typing import Literal

PAGE_SIZE = 6
GRID_COLUMNS = 2

def page_index_for_focus(focus_index: int, *, per_page: int = PAGE_SIZE) -> int:
    """Return page index for a visible-cell focus index."""
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    if focus_index < 0:
        return 0
    return focus_index // per_page


def clamp_focus_index(focus_index: int, *, total: int) -> int:
    """Clamp focus index to visible-cell bounds."""
    if total <= 0:
        return 0
    if focus_index < 0:
        return 0
    if focus_index >= total:
        return total - 1
    return focus_index


def move_focus_linear(focus_index: int, *, total: int, delta: int) -> int:
    """Move focus linearly with wraparound."""
    if total <= 0:
        return 0
    return (focus_index + delta) % total


def move_grid_focus(
    local_index: int,
    *,
    direction: Literal["left", "right", "up", "down"],
    page_len: int,
    columns: int = GRID_COLUMNS,
) -> int:
    """Move focus in a fixed-column page grid without leaving valid slots."""
    if page_len <= 0:
        return 0
    if local_index < 0:
        local_index = 0
    if local_index >= page_len:
        local_index = page_len - 1
    if columns < 1:
        raise ValueError("columns must be >= 1")

    row = local_index // columns
    col = local_index % columns

    if direction == "left":
        candidate = local_index - 1 if col > 0 else local_index
    elif direction == "right":
        candidate = local_index + 1 if col < columns - 1 else local_index
    elif direction == "up":
        candidate = local_index - columns if row > 0 else local_index
    else:
        candidate = local_index + columns

    if candidate < 0 or candidate >= page_len:
        return local_index
    return candidate
