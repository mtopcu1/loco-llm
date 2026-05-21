"""Prompt-toolkit param grid with list/detail views and plain fallback."""
from __future__ import annotations

from llm_cli.core import wizards
from llm_cli.core.param_grid_models import MetaField, ParamCell, ParamGridResult
from llm_cli.core.param_grid_plain import run_param_grid_plain
from llm_cli.core.param_grid_theme import DEFAULT_THEME, ParamGridTheme
from llm_cli.core.param_grid_tui import run_param_grid_tui
from llm_cli.core.param_grid_focus import (
    clamp_focus_index,
    move_focus_linear,
    move_grid_focus,
    page_index_for_focus,
)
from llm_cli.core.params import ParamSpec

def run_param_grid(
    cells: list[ParamCell],
    meta: list[MetaField],
    *,
    specs: list[ParamSpec],
    title: str,
    theme: ParamGridTheme = DEFAULT_THEME,
) -> ParamGridResult:
    """Run prompt-toolkit wizard when interactive, else Rich/plain fallback."""
    try:
        if wizards.use_plain_prompts():
            return run_param_grid_plain(
                cells, meta, specs=specs, title=title, theme=theme
            )
        try:
            return run_param_grid_tui(cells, meta, specs=specs, title=title, theme=theme)
        except ImportError:
            return run_param_grid_plain(
                cells, meta, specs=specs, title=title, theme=theme
            )
    except KeyboardInterrupt:
        return ParamGridResult(
            values={c.key: c.value for c in cells},
            meta={m.key: m.value for m in meta},
            action="abort",
            advanced_revealed=False,
        )
