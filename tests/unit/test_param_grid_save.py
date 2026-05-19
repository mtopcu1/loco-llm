from __future__ import annotations

import pytest

from llm_cli.core.param_grid_build import enabled_values_from_cells
from llm_cli.core.param_grid_models import ParamCell
from llm_cli.core.params import ParamSpec, ParamType, ParamValidationError


def _cell(key: str, *, enabled: bool, value: str, locked: bool = False, ptype=ParamType.INT):
    return ParamCell(
        key=key,
        label=key,
        description="",
        value=value,
        enabled=enabled,
        locked=locked,
        param_type=ptype,
    )


def test_enabled_values_omits_disabled_optional():
    cells = [_cell("ctx", enabled=False, value="")]
    specs = [ParamSpec("ctx", ParamType.INT)]
    assert enabled_values_from_cells(cells, specs) == {}


def test_enabled_values_includes_enabled_with_value():
    cells = [_cell("ctx", enabled=True, value="8192")]
    specs = [ParamSpec("ctx", ParamType.INT)]
    assert enabled_values_from_cells(cells, specs) == {"ctx": "8192"}


def test_enabled_values_rejects_enabled_empty_optional():
    cells = [_cell("ctx", enabled=True, value="")]
    specs = [ParamSpec("ctx", ParamType.INT)]
    with pytest.raises(ParamValidationError, match="ctx"):
        enabled_values_from_cells(cells, specs)


def test_enabled_values_includes_locked_required():
    cells = [_cell("model", enabled=True, value="/path", locked=True, ptype=ParamType.PATH)]
    specs = [ParamSpec("model", ParamType.PATH, required=True)]
    assert enabled_values_from_cells(cells, specs) == {"model": "/path"}


def test_enabled_values_bool_false_is_valid():
    cells = [_cell("flag", enabled=True, value="false", ptype=ParamType.BOOL)]
    specs = [ParamSpec("flag", ParamType.BOOL)]
    assert enabled_values_from_cells(cells, specs) == {"flag": "false"}
