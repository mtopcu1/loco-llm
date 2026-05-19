"""Unit tests for param grid models and Cell list builders."""

from __future__ import annotations

import pytest

from llm_cli.core.model_bindings import MODEL_PATH_TOKEN
from llm_cli.core.param_grid_build import cells_from_specs, filter_visible_cells, paginate_cells
from llm_cli.core.param_grid_models import MetaField, ParamCell, ParamGridResult, cell_state
from llm_cli.core.params import ParamSpec, ParamType


def test_cell_state_disabled() -> None:
    c = ParamCell(
        key="k", label="l", description="", value="", enabled=False, locked=False
    )
    assert cell_state(c) == "disabled"


def test_cell_state_enabled_empty() -> None:
    c = ParamCell(
        key="k", label="l", description="", value="", enabled=True, locked=False
    )
    assert cell_state(c) == "enabled-empty"


def test_cell_state_enabled_set() -> None:
    c = ParamCell(
        key="k", label="l", description="", value="8192", enabled=True, locked=False
    )
    assert cell_state(c) == "enabled-set"


def test_cell_state_locked() -> None:
    c = ParamCell(
        key="k",
        label="l",
        description="",
        value="x",
        enabled=True,
        locked=True,
        readonly=True,
    )
    assert cell_state(c) == "locked"


def test_cells_from_specs_marks_readonly() -> None:
    specs = [
        ParamSpec("a", ParamType.INT, default=1),
        ParamSpec("b", ParamType.STRING, default="x"),
    ]
    cells = cells_from_specs(
        specs,
        values={"a": "1", "b": "x"},
        readonly_keys={"b"},
    )
    assert {c.key: c.readonly for c in cells} == {"a": False, "b": True}


def test_cells_from_specs_skip_keys_prefill_model_binding() -> None:
    specs = [
        ParamSpec(
            "model_arg",
            ParamType.PATH,
            default=None,
            bind="model_path",
        ),
        ParamSpec("other", ParamType.STRING, default="z"),
    ]
    cells = cells_from_specs(
        specs,
        values={},
        skip_keys={"model_arg"},
    )
    model_cell = next(c for c in cells if c.key == "model_arg")
    assert model_cell.value == MODEL_PATH_TOKEN


def test_cells_from_specs_skip_keys_respects_explicit_values() -> None:
    specs = [
        ParamSpec(
            "model_arg",
            ParamType.PATH,
            default=None,
            bind="model_path",
        ),
    ]
    explicit = "/opt/models/foo.gguf"
    cells = cells_from_specs(
        specs,
        values={"model_arg": explicit},
        skip_keys={"model_arg"},
    )
    assert cells[0].value == explicit


def test_paginate_hides_advanced_when_collapsed() -> None:
    cells = [
        ParamCell("k1", "k1", "", "1", enabled=True, tier="common"),
        ParamCell("k2", "k2", "", "2", enabled=True, tier="advanced"),
    ]
    collapsed = paginate_cells(cells, per_page=6, advanced_visible=False)
    assert len(collapsed) == 1 and len(collapsed[0]) == 1
    assert collapsed[0][0].key == "k1"


def test_paginate_includes_advanced_when_visible() -> None:
    cells = [
        ParamCell("k1", "k1", "", "1", enabled=True, tier="common"),
        ParamCell("k2", "k2", "", "2", enabled=True, tier="advanced"),
    ]
    pages = paginate_cells(cells, per_page=6, advanced_visible=True)
    ordered = [c.key for p in pages for c in p]
    assert ordered == ["k1", "k2"]


def test_paginate_six_per_page() -> None:
    cells = [
        ParamCell(f"k{i}", f"k{i}", "", str(i), enabled=True, tier="common")
        for i in range(13)
    ]
    pages = paginate_cells(cells, per_page=6, advanced_visible=True)
    assert len(pages) == 3
    assert len(pages[0]) == 6
    assert len(pages[1]) == 6
    assert len(pages[2]) == 1


def test_paginate_cells_per_page_invalid() -> None:
    with pytest.raises(ValueError):
        paginate_cells([], per_page=0, advanced_visible=True)


def test_filter_visible_cells_hides_readonly() -> None:
    cells = [
        ParamCell("ro", "ro", "", "x", readonly=True, enabled=True, tier="common"),
        ParamCell("ed", "ed", "", "1", readonly=False, enabled=True, tier="common"),
    ]
    visible = filter_visible_cells(cells, advanced_visible=True, hide_readonly=True)
    assert [c.key for c in visible] == ["ed"]


def test_filter_visible_cells_keeps_readonly_when_requested() -> None:
    cells = [ParamCell("ro", "ro", "", "x", readonly=True, enabled=True, tier="common")]
    visible = filter_visible_cells(cells, advanced_visible=True, hide_readonly=False)
    assert [c.key for c in visible] == ["ro"]


def test_param_grid_result_and_meta_shapes() -> None:
    r = ParamGridResult(
        values={"a": "1"},
        meta={"host": "127.0.0.1"},
        action="abort",
        advanced_revealed=True,
    )
    assert r.values["a"] == "1" and r.advanced_revealed is True
    m = MetaField("host", "host", "127.0.0.1", "bind address")
    assert m.description == "bind address"
