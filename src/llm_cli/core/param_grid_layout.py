"""Terminal layout helpers for param grid list and detail views."""

from __future__ import annotations

import textwrap

from llm_cli.core.param_grid_models import ParamCell

INDICATOR_WIDTH = 3


def key_column_width(keys: list[str], terminal_width: int, *, min_width: int = 8) -> int:
    """Width of the key column for aligned list rows."""
    if terminal_width < 20:
        return min_width
    if not keys:
        return min_width
    natural = max(len(k) for k in keys) + 2
    cap = max(min_width, terminal_width // 2)
    return max(min_width, min(natural, cap))


def truncate(value: str, width: int) -> str:
    """Truncate *value* with ellipsis when wider than *width*."""
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "\u2026"


def format_row_pair(key: str, value: str, *, key_width: int, total_width: int) -> tuple[str, str]:
    """Return aligned key and value strings for a list row."""
    gap = 2
    key_part = truncate(key.ljust(key_width), key_width)
    value_width = max(1, total_width - key_width - gap)
    value_part = truncate(value, value_width)
    return key_part, value_part


def value_column_width(
    values: list[str],
    terminal_width: int,
    key_width: int,
    *,
    min_width: int = 6,
) -> int:
    """Width of the value column given key column and terminal size."""
    if terminal_width < 24:
        return min_width
    if not values:
        return min_width
    natural = max(len(v) for v in values) + 2
    remaining = max(min_width, terminal_width - key_width - 6)
    cap = max(min_width, remaining // 2)
    return max(min_width, min(natural, cap))


def cell_indicator(cell: ParamCell) -> str:
    """Row enable indicator: locked [•], enabled [x], disabled [ ]."""
    if cell.locked or cell.readonly:
        return "[\u2022]"
    if cell.enabled:
        return "[x]"
    return "[ ]"


def suggestion_column_width(
    suggestions: list[str],
    terminal_width: int,
    key_width: int,
    val_width: int,
    *,
    min_width: int = 6,
) -> int:
    """Width of the suggestion column given other fixed columns."""
    if terminal_width < 32:
        return min_width
    if not suggestions:
        return min_width
    natural = max(len(s) for s in suggestions) + 2
    fixed = INDICATOR_WIDTH + key_width + val_width + 8
    remaining = max(min_width, terminal_width - fixed)
    return max(min_width, min(natural, remaining // 2))


def format_param_row(
    indicator: str,
    key: str,
    value: str,
    suggestion: str,
    *,
    key_width: int,
    val_width: int,
    sug_width: int,
    total_width: int,
) -> tuple[str, str, str, str]:
    """Return aligned indicator, key, value, and suggestion for a param list row."""
    gap = 2
    marker = 1
    ind_part = truncate(indicator.ljust(INDICATOR_WIDTH), INDICATOR_WIDTH)
    key_part = truncate(key.ljust(key_width), key_width)
    val_part = truncate(value.ljust(val_width), val_width)
    sug_width = max(0, sug_width)
    used = marker + INDICATOR_WIDTH + key_width + val_width + (gap * 3)
    desc_width = total_width - used
    if desc_width < 1 or not suggestion:
        sug_part = ""
    else:
        sug_part = truncate(suggestion, min(sug_width, desc_width))
    return ind_part, key_part, val_part, sug_part


def format_row_triple(
    key: str,
    value: str,
    description: str,
    *,
    key_width: int,
    val_width: int,
    total_width: int,
) -> tuple[str, str, str]:
    """Return aligned key, value, and truncated description for a list row."""
    gap = 2
    marker = 1
    key_part = truncate(key.ljust(key_width), key_width)
    val_part = truncate(value.ljust(val_width), val_width)
    desc_width = total_width - marker - key_width - val_width - (gap * 2)
    if desc_width < 1:
        desc_part = ""
    else:
        desc_part = truncate(description, desc_width)
    return key_part, val_part, desc_part


def wrap_lines(text: str, width: int) -> list[str]:
    """Word-wrap *text* to *width*; empty input yields empty list."""
    stripped = (text or "").strip()
    if not stripped:
        return []
    if width < 1:
        return [stripped]
    return textwrap.wrap(stripped, width=width) or [stripped]


def scroll_offset_for_focus(
    focus_index: int,
    *,
    total_rows: int,
    viewport_rows: int,
    current_offset: int,
) -> int:
    """Keep *focus_index* visible inside a viewport of *viewport_rows*."""
    if viewport_rows < 1 or total_rows <= viewport_rows:
        return 0
    offset = current_offset
    if focus_index < offset:
        offset = focus_index
    elif focus_index >= offset + viewport_rows:
        offset = focus_index - viewport_rows + 1
    max_offset = max(0, total_rows - viewport_rows)
    return min(offset, max_offset)
