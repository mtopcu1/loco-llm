"""Reusable key sequences for param-grid wizards."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.model_bindings import bound_keys_to_skip
from llm_cli.core.param_grid_build import cells_from_specs, filter_visible_cells
from llm_cli.core.registry import get_runtime_manifest

from tests.tui import keys as k
from tests.tui.session import TuiSession


def visible_param_row_count(
    repo_root: Path,
    runtime_id: str,
    *,
    model_id: str | None,
    advanced: bool = False,
) -> int:
    manifest = get_runtime_manifest(repo_root, runtime_id)
    assert manifest is not None
    skip = bound_keys_to_skip(manifest.serve_schema, model_id=model_id)
    cells = cells_from_specs(
        manifest.serve_schema,
        skip_keys=skip,
        readonly_keys=skip,
    )
    return len(
        filter_visible_cells(
            cells,
            advanced_visible=advanced,
            hide_readonly=True,
        )
    )


def advance_meta_to_params(session: TuiSession) -> None:
    session.expect("Configuration", timeout=20)
    session.send(k.RIGHT)


def save_params_via_footer(
    session: TuiSession,
    *,
    repo_root: Path,
    runtime_id: str,
    model_id: str | None = None,
    expect_params: bool = True,
) -> None:
    """Move focus to footer Save and activate (avoids Ctrl+S / ixon issues)."""
    if expect_params:
        session.expect("Parameters", timeout=20)
    rows = visible_param_row_count(repo_root, runtime_id, model_id=model_id)
    for _ in range(max(0, rows - 1)):
        session.send(k.DOWN)
    session.send(k.DOWN)
    session.send(k.RIGHT)
    session.send(k.ENTER)


def abort_wizard(session: TuiSession, *, from_params: bool = False) -> None:
    """Abort param-grid wizard (Esc on meta; Esc×2 from params)."""
    if from_params:
        session.send(k.ESC)
        session.expect("Configuration", timeout=10)
    session.send(k.ESC)
    session.expect("aborted", timeout=15)


def save_empty_params(session: TuiSession) -> None:
    """Save when the params list has zero visible rows."""
    session.expect("Parameters", timeout=20)
    session.send(k.DOWN)
    session.send(k.RIGHT)
    session.send(k.ENTER)
