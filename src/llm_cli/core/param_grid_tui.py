"""Prompt-toolkit param grid TUI (list/detail state machine)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from llm_cli.core.param_grid_build import (
    enabled_values_from_cells,
    filter_cells_by_query,
    filter_visible_cells,
)
from llm_cli.core.param_grid_layout import (
    cell_indicator,
    format_param_row,
    format_row_triple,
    key_column_width,
    scroll_offset_for_focus,
    suggestion_column_width,
    value_column_width,
    wrap_lines,
)
from llm_cli.core.param_grid_models import MetaField, ParamCell, ParamGridResult, cell_state
from llm_cli.core.param_grid_theme import DEFAULT_THEME, ParamGridTheme, style_for_cell_state
from llm_cli.core.params import ParamSpec, ParamType, ParamValidationError, coerce_value
from llm_cli.core.wizard_shell import (
    ShellFocus,
    footer_next_label,
    move_content,
    move_content_down,
    render_footer,
    toggle_footer_button,
)

def _spec_for_cell(cell: ParamCell):
    from llm_cli.core.params import ParamSpec

    return ParamSpec(key=cell.key, type=cell.param_type)


def _coerce_and_format(cell: ParamCell, raw: str) -> str:
    if cell.param_type is ParamType.ENUM:
        return str(raw)
    coerced = coerce_value(_spec_for_cell(cell), raw)
    return str(coerced)


@dataclass
class _WizardState:
    phase: Literal["meta", "list", "detail"]
    advanced_visible: bool = False
    focus: ShellFocus = field(default_factory=ShellFocus)
    detail_kind: Literal["meta", "cell"] = "cell"
    editing: bool = False
    edit_buffer: str = ""
    error_message: str = ""
    filter_text: str = ""
    filter_editing: bool = False


def run_param_grid_tui(
    cells: list[ParamCell],
    meta: list[MetaField],
    *,
    specs: list[ParamSpec],
    title: str,
    theme: ParamGridTheme = DEFAULT_THEME,
) -> ParamGridResult:
    """Run list/detail param wizard with optional meta form step."""
    try:
        from prompt_toolkit.application import Application, get_app
        from prompt_toolkit.formatted_text import StyleAndTextTuples
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.keys import Keys
        from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.styles import Style
    except ImportError as exc:
        raise ImportError("prompt_toolkit is unavailable") from exc

    initial_phase: Literal["meta", "list"] = "meta" if meta else "list"
    state = _WizardState(phase=initial_phase)

    def _terminal_size() -> tuple[int, int]:
        try:
            size = get_app().output.get_size()
            return max(40, size.columns), max(10, size.rows)
        except Exception:
            return 80, 24

    def _visible_param_cells() -> list[ParamCell]:
        return filter_visible_cells(
            cells,
            advanced_visible=state.advanced_visible,
            hide_readonly=True,
        )

    def _list_param_cells() -> list[ParamCell]:
        visible = _visible_param_cells()
        if state.phase != "list" or not state.filter_text.strip():
            return visible
        return filter_cells_by_query(visible, state.filter_text)

    def _reset_filter_focus() -> None:
        state.focus.content_index = 0
        state.focus.scroll_offset = 0
        state.focus.zone = "content"

    def _set_filter_text(text: str) -> None:
        if text == state.filter_text:
            return
        state.filter_text = text
        _reset_filter_focus()
        _ensure_focus_bounds()

    def _clear_filter() -> None:
        state.filter_editing = False
        if state.filter_text:
            _set_filter_text("")
        else:
            _reset_filter_focus()

    def _content_row_count() -> int:
        if state.phase == "meta":
            return len(meta)
        if state.phase == "list":
            return len(_list_param_cells())
        return 1

    def _ensure_focus_bounds() -> None:
        total = _content_row_count()
        if state.focus.content_index >= total and total > 0:
            state.focus.content_index = total - 1
        if total == 0 and state.focus.zone == "content":
            state.focus.zone = "footer"

    def _set_error(message: str) -> None:
        state.error_message = message

    def _clear_error() -> None:
        state.error_message = ""

    def _viewport_rows(*, reserved: int = 4) -> int:
        _cols, rows = _terminal_size()
        return max(1, rows - reserved)

    def _update_scroll() -> None:
        total = _content_row_count()
        viewport = _viewport_rows()
        state.focus.scroll_offset = scroll_offset_for_focus(
            state.focus.content_index,
            total_rows=total,
            viewport_rows=viewport,
            current_offset=state.focus.scroll_offset,
        )

    def _enter_detail(*, kind: Literal["meta", "cell"], index: int) -> None:
        state.phase = "detail"
        state.detail_kind = kind
        state.focus.content_index = index
        state.focus.zone = "content"
        state.editing = True
        if kind == "meta":
            state.edit_buffer = meta[index].value
        else:
            state.edit_buffer = _list_param_cells()[index].value
        _clear_error()

    def _cancel_detail() -> None:
        state.editing = False
        state.edit_buffer = ""
        state.phase = "meta" if state.detail_kind == "meta" else "list"
        _clear_error()

    def _commit_detail() -> bool:
        raw = state.edit_buffer
        if state.detail_kind == "meta":
            field = meta[state.focus.content_index]
            if field.key == "port":
                try:
                    int(raw.strip())
                except ValueError:
                    _set_error("port must be an integer")
                    return False
            if not raw.strip() and field.key in ("host", "preset", "config_id"):
                _set_error(f"{field.key} must not be empty")
                return False
            field.value = raw
        else:
            visible = _list_param_cells()
            cell = visible[state.focus.content_index]
            try:
                cell.value = _coerce_and_format(cell, raw)
            except ParamValidationError as exc:
                _set_error(str(exc))
                return False
        state.editing = False
        state.edit_buffer = ""
        state.phase = "meta" if state.detail_kind == "meta" else "list"
        _clear_error()
        return True

    def _validate_meta() -> str | None:
        for field in meta:
            if field.key == "port":
                try:
                    int(field.value.strip())
                except ValueError:
                    return "port must be an integer"
            if not field.value.strip() and field.key in ("host", "preset", "config_id"):
                return f"{field.key} must not be empty"
        return None

    def _exit_save() -> None:
        try:
            filtered = enabled_values_from_cells(cells, specs)
        except ParamValidationError as exc:
            _set_error(str(exc))
            return
        for cell in cells:
            if not (cell.enabled or cell.locked):
                continue
            try:
                _coerce_and_format(cell, cell.value)
            except ParamValidationError as exc:
                _set_error(f"{cell.key}: {exc}")
                return
        app.exit(
            result=ParamGridResult(
                values=filtered,
                meta={m.key: m.value for m in meta},
                action="save",
                advanced_revealed=state.advanced_visible,
            )
        )

    def _exit_abort() -> None:
        app.exit(
            result=ParamGridResult(
                values={c.key: c.value for c in cells},
                meta={m.key: m.value for m in meta},
                action="abort",
                advanced_revealed=state.advanced_visible,
            )
        )

    def _navigate_page_back() -> None:
        """← : previous wizard page only (never abort/save)."""
        if state.phase == "list" and meta:
            state.filter_editing = False
            state.filter_text = ""
            state.phase = "meta"
            state.focus = ShellFocus()
            _clear_error()

    def _navigate_page_next() -> None:
        """→ : next wizard page only (never abort/save)."""
        if state.phase == "meta" and meta:
            err = _validate_meta()
            if err is not None:
                _set_error(err)
                return
            state.phase = "list"
            state.focus = ShellFocus()
            _clear_error()

    def _wizard_back() -> None:
        if state.phase == "detail":
            _cancel_detail()
            return
        if state.phase == "meta":
            _exit_abort()
            return
        if state.phase == "list":
            if meta:
                state.filter_editing = False
                state.filter_text = ""
                state.phase = "meta"
                state.focus = ShellFocus()
                _clear_error()
            else:
                _exit_abort()

    def _wizard_next() -> None:
        if state.phase == "detail":
            _commit_detail()
            return
        if state.phase == "meta":
            err = _validate_meta()
            if err is not None:
                _set_error(err)
                return
            state.phase = "list"
            state.focus = ShellFocus()
            _clear_error()
            return
        if state.phase == "list":
            _exit_save()

    def _activate_footer() -> None:
        if state.focus.footer_button == "back":
            _wizard_back()
        else:
            _wizard_next()

    def _toggle_enable_at(index: int) -> None:
        visible = _list_param_cells()
        if index < 0 or index >= len(visible):
            return
        cell = visible[index]
        if cell.locked or cell.readonly:
            return
        cell.enabled = not cell.enabled
        if not cell.enabled:
            cell.value = ""
        _clear_error()

    def _render_header() -> StyleAndTextTuples:
        cols, _rows = _terminal_size()
        advanced_state = "ON" if state.advanced_visible else "OFF"
        if state.phase == "meta":
            subtitle = "Configuration"
        elif state.phase == "detail":
            subtitle = "Edit"
        else:
            subtitle = "Parameters"
        line = f"{title} — {subtitle}  ·  Advanced: {advanced_state}"
        if len(line) > cols:
            line = line[: cols - 1] + "\u2026"
        return [("class:text", line)]

    def _style_class(row_state: str) -> str:
        if row_state == "text":
            return "class:text"
        return f"class:{style_for_cell_state(row_state)}"

    def _render_list_rows(
        rows: list[tuple[str, str, str, str]],
    ) -> StyleAndTextTuples:
        cols, _rows = _terminal_size()
        viewport = _viewport_rows()
        keys = [r[0] for r in rows]
        values = [r[1] for r in rows]
        key_w = key_column_width(keys, cols)
        val_w = value_column_width(values, cols, key_w)
        out: StyleAndTextTuples = []
        start = state.focus.scroll_offset
        end = min(len(rows), start + viewport)
        for idx in range(start, end):
            key, value, description, row_state = rows[idx]
            focused = state.focus.zone == "content" and state.focus.content_index == idx
            row_cls = _style_class(row_state)
            key_cls = "class:cell-focus" if focused else row_cls
            val_cls = key_cls
            key_txt, val_txt, desc_txt = format_row_triple(
                key,
                value,
                description,
                key_width=key_w,
                val_width=val_w,
                total_width=cols,
            )
            prefix = ">" if focused else " "
            out.append(("class:text-dim", prefix))
            out.append((key_cls, key_txt))
            out.append(("class:text-dim", "  "))
            out.append((val_cls, val_txt))
            if desc_txt:
                out.append(("class:text-dim", "  "))
                desc_cls = "class:text-dim" if not focused else "class:hint"
                out.append((desc_cls, desc_txt))
            out.append(("", "\n"))
        if not rows:
            out.append(("class:text-dim", "(no editable parameters)\n"))
        return out

    def _render_meta_list() -> StyleAndTextTuples:
        rows = [(m.label, m.value, m.description, "text") for m in meta]
        return _render_list_rows(rows)

    def _render_filter_bar() -> StyleAndTextTuples:
        if state.phase != "list":
            return [("class:text-dim", "")]
        if not state.filter_editing and not state.filter_text:
            return [("class:text-dim", "")]
        cols, _rows = _terminal_size()
        matches = len(_list_param_cells())
        match_note = f" ({matches} match{'es' if matches != 1 else ''})"
        cursor = "█" if state.filter_editing else ""
        line = f"Filter: {state.filter_text}{cursor}{match_note}"
        if len(line) > cols:
            line = line[: cols - 1] + "\u2026"
        return [("class:hint", line)]

    def _render_param_list() -> StyleAndTextTuples:
        visible = _list_param_cells()
        cols, _rows = _terminal_size()
        viewport = _viewport_rows()
        keys = [c.key for c in visible]
        values = [c.value for c in visible]
        suggestions = [c.hint or "" for c in visible]
        key_w = key_column_width(keys, cols)
        val_w = value_column_width(values, cols, key_w)
        sug_w = suggestion_column_width(suggestions, cols, key_w, val_w)
        out: StyleAndTextTuples = []
        start = state.focus.scroll_offset
        end = min(len(visible), start + viewport)
        for idx in range(start, end):
            cell = visible[idx]
            state_name = cell_state(cell)
            row_cls = _style_class(state_name)
            focused = state.focus.zone == "content" and state.focus.content_index == idx
            key_cls = "class:cell-focus" if focused else row_cls
            val_cls = key_cls
            ind_txt, key_txt, val_txt, sug_txt = format_param_row(
                cell_indicator(cell),
                cell.key,
                cell.value,
                cell.hint or "",
                key_width=key_w,
                val_width=val_w,
                sug_width=sug_w,
                total_width=cols,
            )
            prefix = ">" if focused else " "
            out.append(("class:text-dim", prefix))
            out.append((key_cls, ind_txt))
            out.append(("class:text-dim", "  "))
            out.append((key_cls, key_txt))
            out.append(("class:text-dim", "  "))
            out.append((val_cls, val_txt))
            if sug_txt:
                out.append(("class:text-dim", "  "))
                sug_cls = "class:hint" if focused else "class:text-dim"
                out.append((sug_cls, sug_txt))
            out.append(("", "\n"))
        if not visible:
            if state.filter_text.strip():
                out.append(("class:text-dim", "(no parameters match filter)\n"))
            else:
                out.append(("class:text-dim", "(no editable parameters)\n"))
        return out

    def _render_detail() -> StyleAndTextTuples:
        cols, _rows = _terminal_size()
        wrap_w = max(20, cols - 4)
        out: StyleAndTextTuples = []

        if state.detail_kind == "meta":
            field = meta[state.focus.content_index]
            key = field.label
            description = field.description
            hint = None
        else:
            cell = _list_param_cells()[state.focus.content_index]
            key = cell.key
            description = cell.description
            hint = cell.hint

        out.append(("class:text", f"{key}\n\n"))
        for line in wrap_lines(description, wrap_w):
            out.append(("class:text-dim", line + "\n"))
        if hint:
            out.append(("", "\n"))
            for line in wrap_lines(f"Suggestion: {hint}", wrap_w):
                out.append(("class:hint", line + "\n"))
        out.append(("", "\n"))
        out.append(("class:text", "Value: "))
        out.append(("class:cell-focus", state.edit_buffer + ("█" if state.editing else "")))
        out.append(("", "\n"))
        return out

    def _render_content() -> StyleAndTextTuples:
        _update_scroll()
        if state.phase == "detail":
            return _render_detail()
        if state.phase == "meta":
            return _render_meta_list()
        return _render_param_list()

    def _render_chrome() -> StyleAndTextTuples:
        in_footer = state.focus.zone == "footer"
        return render_footer(
            focused_button=state.focus.footer_button,
            in_footer=in_footer,
            next_label=footer_next_label(phase=state.phase, has_meta=bool(meta)),
        )

    kb = KeyBindings()

    @kb.add("up")
    def _up(_event) -> None:
        if state.filter_editing:
            state.filter_editing = False
        if state.phase == "detail" and state.editing:
            return
        if state.focus.zone == "footer":
            state.focus.zone = "content"
            _ensure_focus_bounds()
            return
        total = _content_row_count()
        if state.focus.content_index > 0:
            state.focus.content_index -= 1
        elif total > 0:
            state.focus.content_index = 0

    @kb.add("down")
    def _down(_event) -> None:
        if state.filter_editing:
            state.filter_editing = False
        if state.phase == "detail" and state.editing:
            if state.focus.zone == "content":
                state.focus.zone = "footer"
                state.focus.footer_button = "next"
            return
        total = _content_row_count()
        move_content_down(state.focus, total=total)

    @kb.add("left")
    def _left(_event) -> None:
        if state.phase == "detail" and state.editing:
            return
        if state.focus.zone == "footer":
            state.focus.footer_button = "back"
            return
        if state.phase in ("meta", "list") and state.focus.zone == "content":
            _navigate_page_back()

    @kb.add("right")
    def _right(_event) -> None:
        if state.phase == "detail" and state.editing:
            return
        if state.focus.zone == "footer":
            state.focus.footer_button = "next"
            return
        if state.phase in ("meta", "list") and state.focus.zone == "content":
            _navigate_page_next()

    @kb.add("tab")
    def _tab(_event) -> None:
        if state.phase == "detail" and state.editing:
            state.edit_buffer += "    "
            return
        if state.focus.zone == "footer":
            toggle_footer_button(state.focus)
        else:
            total = _content_row_count()
            move_content(state.focus, +1, total=total)

    @kb.add("s-tab")
    def _shift_tab(_event) -> None:
        if state.focus.zone == "footer":
            toggle_footer_button(state.focus)
        else:
            total = _content_row_count()
            move_content(state.focus, -1, total=total)

    @kb.add("enter")
    def _enter(_event) -> None:
        if state.filter_editing:
            state.filter_editing = False
            return
        if state.focus.zone == "footer":
            _activate_footer()
            return
        if state.phase == "detail":
            _commit_detail()
            return
        if state.phase == "meta":
            _enter_detail(kind="meta", index=state.focus.content_index)
            return
        _enter_detail(kind="cell", index=state.focus.content_index)

    @kb.add("escape")
    def _escape(_event) -> None:
        if state.filter_editing or state.filter_text:
            _clear_filter()
            return
        if state.phase == "detail":
            _cancel_detail()
            return
        _wizard_back()

    @kb.add("c-f")
    def _ctrl_f(_event) -> None:
        if state.phase != "list":
            return
        state.filter_editing = True
        state.focus.zone = "content"
        _clear_error()

    @kb.add("c-s")
    def _ctrl_s(_event) -> None:
        if state.phase == "detail":
            _commit_detail()
            return
        _wizard_next()

    @kb.add("c-x")
    def _ctrl_x(_event) -> None:
        _exit_abort()

    @kb.add("c-c")
    @kb.add("<sigint>")
    def _ctrl_c(_event) -> None:
        _exit_abort()

    @kb.add("c-a")
    def _ctrl_a(_event) -> None:
        if state.phase != "list":
            return
        state.advanced_visible = not state.advanced_visible
        _ensure_focus_bounds()
        _clear_error()

    @kb.add(" ")
    def _space(_event) -> None:
        if state.filter_editing:
            _set_filter_text(state.filter_text + " ")
            return
        if state.phase == "detail" and state.editing:
            state.edit_buffer += " "
            return
        if state.phase == "list" and state.focus.zone == "content":
            _toggle_enable_at(state.focus.content_index)

    @kb.add("backspace")
    def _backspace(_event) -> None:
        if state.filter_editing:
            _set_filter_text(state.filter_text[:-1])
            return
        if state.phase == "detail" and state.editing:
            state.edit_buffer = state.edit_buffer[:-1]

    @kb.add(Keys.Any)
    def _typed(event) -> None:
        if state.filter_editing and event.data:
            _set_filter_text(state.filter_text + event.data)
            return
        if state.phase == "detail" and state.editing and event.data:
            state.edit_buffer += event.data

    header = Window(FormattedTextControl(_render_header), height=1)
    filter_bar = ConditionalContainer(
        Window(FormattedTextControl(_render_filter_bar), height=1),
        filter=Condition(
            lambda: state.phase == "list"
            and (state.filter_editing or bool(state.filter_text))
        ),
    )
    content = Window(FormattedTextControl(_render_content), height=Dimension(weight=1))
    error_window = Window(
        FormattedTextControl(
            lambda: [("class:error", state.error_message)] if state.error_message else [("class:text-dim", "")]
        ),
        height=1,
    )
    footer = Window(FormattedTextControl(_render_chrome), height=1)
    hint = Window(
        FormattedTextControl(
            lambda: [
                (
                    "class:text-dim",
                    "↑↓ rows · Space enable · Ctrl+F filter · ←→ pages · Enter detail · Esc Back · Ctrl+S Save",
                )
            ]
        ),
        height=1,
    )

    root = HSplit([header, filter_bar, content, error_window, footer, hint])
    style = Style.from_dict(theme.to_prompt_toolkit_style())
    app = Application(
        layout=Layout(root),
        key_bindings=kb,
        style=style,
        full_screen=True,
        mouse_support=False,
    )
    _ensure_focus_bounds()
    return app.run()
