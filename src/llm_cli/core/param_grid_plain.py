"""Rich table + numbered menu fallback for param grids (non–prompt_toolkit)."""

from __future__ import annotations

from typing import Literal

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

from llm_cli.core.param_grid_build import enabled_values_from_cells, filter_cells_by_query, filter_visible_cells
from llm_cli.core.param_grid_layout import cell_indicator, truncate
from llm_cli.core.param_grid_models import MetaField, ParamCell, ParamGridResult, cell_state
from llm_cli.core.param_grid_theme import DEFAULT_THEME, ParamGridTheme
from llm_cli.core.params import ParamSpec, ParamType, ParamValidationError, coerce_value

StepResult = Literal["save", "abort"]


def _spec_for_cell(cell: ParamCell) -> ParamSpec:
    return ParamSpec(key=cell.key, type=cell.param_type)


def _coerce_and_format(cell: ParamCell, raw: str) -> str:
    if cell.param_type is ParamType.ENUM:
        return str(raw)
    spec = _spec_for_cell(cell)
    coerced = coerce_value(spec, raw)
    return str(coerced)


def _display_value(cell: ParamCell) -> str:
    if cell.locked or cell.readonly:
        return cell.value or "—"
    if not cell.enabled:
        return "(off)"
    return cell.value


def _render_value_markup(cell: ParamCell, theme: ParamGridTheme) -> str:
    return f"{theme.rich(cell_state(cell))}{escape(_display_value(cell))}[/]"


def _validate_meta(meta: list[MetaField]) -> str | None:
    for field in meta:
        if field.key == "port":
            try:
                int(field.value.strip())
            except ValueError:
                return "port must be an integer"
        if not field.value.strip() and field.key in ("host", "preset", "config_id"):
            return f"{field.key} must not be empty"
    return None


def _run_meta_step(
    meta: list[MetaField],
    *,
    title: str,
    theme: ParamGridTheme,
    console: Console,
) -> StepResult:
    while True:
        table = Table(title=f"{title} — Configuration", show_header=True, header_style="bold")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Field")
        table.add_column("Value")
        table.add_column("Description", style="dim")

        for i, field in enumerate(meta, start=1):
            table.add_row(
                str(i),
                escape(field.label),
                escape(field.value),
                escape(truncate(field.description, 40)) if field.description else "—",
            )

        console.print(table)
        console.print(
            f"{theme.rich('hint')}"
            f"Row number = edit · N = next · X = abort[/]"
        )
        choice = Prompt.ask(theme.rich("text") + "Command[/]").strip().lower()
        if choice == "x":
            return "abort"
        if choice in ("n", "s"):
            err = _validate_meta(meta)
            if err:
                console.print(f"{theme.rich('error')}{escape(err)}[/]")
                continue
            return "save"
        if not choice.isdigit():
            console.print(f"{theme.rich('error')}Unknown command {choice!r}.[/]")
            continue
        idx = int(choice)
        if idx < 1 or idx > len(meta):
            console.print(f"{theme.rich('error')}No row {idx}.[/]")
            continue
        field = meta[idx - 1]
        if field.description:
            console.print(f"{theme.rich('dim')}{escape(field.description)}[/]")
        new_raw = Prompt.ask(
            f"{theme.rich('text')}{escape(field.label)}[/]",
            default=field.value,
        )
        if field.key == "port":
            try:
                int(new_raw.strip())
            except ValueError:
                console.print(f"{theme.rich('error')}port must be an integer[/]")
                continue
        field.value = new_raw


def _toggle_enable_cell(
    cell: ParamCell,
    *,
    theme: ParamGridTheme,
    console: Console,
) -> None:
    if cell.locked or cell.readonly:
        console.print(f"{theme.rich('error')}{escape(cell.key)} is read-only.[/]")
        return
    if cell.enabled:
        cell.enabled = False
        cell.value = ""
        return
    if cell.description:
        console.print(f"{theme.rich('dim')}{escape(cell.description)}[/]")
    if cell.hint:
        console.print(f"{theme.rich('hint')}Suggestion: {escape(cell.hint)}[/]")
    default_val = cell.value if cell.value else None
    new_raw = Prompt.ask(
        f"{theme.rich('text')}{escape(cell.key)}[/]",
        default=default_val,
    )
    try:
        cell.value = _coerce_and_format(cell, new_raw)
    except ParamValidationError as exc:
        console.print(f"{theme.rich('error')}{escape(str(exc))}[/]")
        return
    cell.enabled = True


def _save_result(
    cells: list[ParamCell],
    specs: list[ParamSpec],
    meta_map: dict[str, str],
    *,
    advanced_visible: bool,
) -> ParamGridResult | str:
    """Build save result, or return an error message string."""
    try:
        filtered = enabled_values_from_cells(cells, specs)
    except ParamValidationError as exc:
        return str(exc)
    for cell in cells:
        if not (cell.enabled or cell.locked):
            continue
        try:
            _coerce_and_format(cell, cell.value)
        except ParamValidationError as exc:
            return f"{cell.key}: {exc}"
    return ParamGridResult(
        values=filtered,
        meta=dict(meta_map),
        action="save",
        advanced_revealed=advanced_visible,
    )


def run_param_grid_plain(
    cells: list[ParamCell],
    meta: list[MetaField],
    *,
    specs: list[ParamSpec] | None = None,
    title: str,
    theme: ParamGridTheme = DEFAULT_THEME,
    console: Console | None = None,
) -> ParamGridResult:
    """Two-step Rich wizard: optional meta form, then param list."""
    spec_list = list(specs or [])
    con = console if console is not None else Console()
    advanced_visible = False
    filter_query = ""
    meta_map = {m.key: m.value for m in meta}

    if meta:
        step = _run_meta_step(meta, title=title, theme=theme, console=con)
        if step == "abort":
            return ParamGridResult(
                values={c.key: c.value for c in cells},
                meta=dict(meta_map),
                action="abort",
                advanced_revealed=False,
            )
        meta_map = {m.key: m.value for m in meta}

    while True:
        visible = filter_visible_cells(
            cells,
            advanced_visible=advanced_visible,
            hide_readonly=True,
        )
        if filter_query.strip():
            visible = filter_cells_by_query(visible, filter_query)
        table = Table(title=f"{title} — Parameters", show_header=True, header_style="bold")
        table.add_column("#", justify="right", style="dim")
        table.add_column("", justify="center", style="dim")
        table.add_column("Key")
        table.add_column("Value")
        table.add_column("Description", style="dim")

        for i, cell in enumerate(visible, start=1):
            table.add_row(
                str(i),
                escape(cell_indicator(cell)),
                escape(cell.key),
                _render_value_markup(cell, theme),
                escape(truncate(cell.description, 40)) if cell.description else "—",
            )

        con.print(table)
        if filter_query.strip():
            con.print(
                f"{theme.rich('hint')}Filter: {escape(filter_query)} "
                f"({len(visible)} match{'es' if len(visible) != 1 else ''})[/]"
            )
        legend = (
            f"{theme.rich('hint')}"
            f"Number = enable · F = filter · A = advanced · B = back · S = save · X = abort[/]"
        )
        con.print(legend)

        choice_raw = Prompt.ask(theme.rich("text") + "Command[/]").strip()
        choice = choice_raw.lower()
        if not choice:
            con.print(f"{theme.rich('error')}Nothing entered; try again.[/]")
            continue

        if choice == "a":
            advanced_visible = not advanced_visible
            continue
        if choice == "f":
            filter_query = Prompt.ask(
                f"{theme.rich('text')}Filter[/] (empty to clear)",
                default=filter_query,
            )
            continue
        if choice == "b":
            if meta:
                step = _run_meta_step(meta, title=title, theme=theme, console=con)
                if step == "abort":
                    return ParamGridResult(
                        values={c.key: c.value for c in cells},
                        meta=dict(meta_map),
                        action="abort",
                        advanced_revealed=advanced_visible,
                    )
                meta_map = {m.key: m.value for m in meta}
            continue
        if choice == "s":
            outcome = _save_result(
                cells,
                spec_list,
                meta_map,
                advanced_visible=advanced_visible,
            )
            if isinstance(outcome, str):
                con.print(f"{theme.rich('error')}{escape(outcome)}[/]")
                continue
            return outcome
        if choice == "x":
            return ParamGridResult(
                values={c.key: c.value for c in cells},
                meta=dict(meta_map),
                action="abort",
                advanced_revealed=advanced_visible,
            )

        if not choice.isdigit():
            con.print(f"{theme.rich('error')}Unknown command {choice_raw!r}.[/]")
            continue

        idx = int(choice)
        if idx < 1 or idx > len(visible):
            con.print(
                f"{theme.rich('error')}"
                f"No row {idx}; valid 1–{len(visible)}.[/]"
            )
            continue

        cell = visible[idx - 1]
        _toggle_enable_cell(cell, theme=theme, console=con)
