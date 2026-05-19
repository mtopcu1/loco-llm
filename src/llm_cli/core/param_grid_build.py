"""Build paginated ParamCell grids from runtime ParamSpecs."""

from __future__ import annotations

from llm_cli.core.model_bindings import MODEL_PATH_TOKEN
from llm_cli.core.param_grid_models import ParamCell
from llm_cli.core.params import ParamSpec


def cells_from_specs(
    specs: list[ParamSpec],
    *,
    values: dict[str, str] | None = None,
    skip_keys: set[str] | None = None,
    readonly_keys: set[str] | None = None,
    hints: dict[str, str] | None = None,
) -> list[ParamCell]:
    """Materialize grid cells; pre-fill skip_keys (bound model path token, etc.)."""
    merged: dict[str, str] = dict(values or {})
    skip = skip_keys or set()
    hints = hints or {}
    readonly_keys = readonly_keys or set()

    for spec in specs:
        if spec.key not in skip:
            continue
        if spec.key not in merged and spec.bind == "model_path":
            merged[spec.key] = MODEL_PATH_TOKEN

    out: list[ParamCell] = []
    for spec in specs:
        locked = spec.required or spec.key in readonly_keys or spec.key in skip
        if spec.key in merged:
            value_s = merged[spec.key]
            enabled = True
        elif locked:
            value_s = merged.get(spec.key, "")
            enabled = True
        else:
            value_s = ""
            enabled = False

        label = (spec.prompt or spec.key).strip() or spec.key
        out.append(
            ParamCell(
                key=spec.key,
                label=label,
                description=spec.description or "",
                value=value_s,
                enabled=enabled,
                locked=locked,
                readonly=spec.key in readonly_keys or spec.key in skip,
                tier=spec.tier,
                hint=hints.get(spec.key),
                param_type=spec.type,
            )
        )
    return out


def filter_visible_cells(
    cells: list[ParamCell],
    *,
    advanced_visible: bool,
    hide_readonly: bool = True,
) -> list[ParamCell]:
    """Return cells shown in list navigation (tier + optional readonly filter)."""
    out: list[ParamCell] = []
    for cell in cells:
        if not advanced_visible and cell.tier == "advanced":
            continue
        if hide_readonly and cell.readonly:
            continue
        out.append(cell)
    return out


def paginate_cells(
    cells: list[ParamCell],
    *,
    per_page: int = 6,
    advanced_visible: bool,
    hide_readonly: bool = False,
) -> list[list[ParamCell]]:
    """Return pages of cells; excludes advanced tier when not visible."""
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    filtered = filter_visible_cells(
        cells,
        advanced_visible=advanced_visible,
        hide_readonly=hide_readonly,
    )
    if not filtered:
        return []

    pages: list[list[ParamCell]] = []
    for start in range(0, len(filtered), per_page):
        pages.append(filtered[start : start + per_page])
    return pages
