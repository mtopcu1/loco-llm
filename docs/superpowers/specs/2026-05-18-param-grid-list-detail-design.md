# Param Grid List/Detail + Wizard Shell Design

**Date:** 2026-05-18  
**Status:** Approved

## Problem

The current param grid TUI packs description, hints, and values into a 2×3 card layout. Readonly bound fields (e.g. `gguf_path` on presets) clutter the view. Hints overflow columns. Inline Enter editing gives no clear “inside this field” feedback. Meta fields (`host`, `port`, `preset`, `config_id`) sit in a header bar and are not edited in a dedicated step.

## Goals

1. **Two-step config wizard:** meta form → params list (params-only on step 2).
2. **List navigation view:** one line per param — `key` + `value` only; hide readonly rows from the list (values still saved).
3. **Detail view:** Enter opens full-screen body for one param — description, suggestion, value editor; Enter commits, Esc cancels back to list.
4. **Bool params:** Space toggles in list (no detail).
5. **Wizard chrome:** Back and Next footer on all wizard-style masks; focus ladder (content → Down on last row → footer).
6. **Dynamic layout:** column widths derived from terminal size; wrapped text in detail only.
7. **Plain fallback:** same two-step flow and semantics on non-TTY.

## Non-goals

- Changing YAML output shape or validation rules in `config_cmd`.
- Mouse-first UX (keyboard remains primary; mouse optional later).
- Replacing questionary for simple `select`/`confirm` prompts outside the grid.

## Architecture

### Modules

| Module | Responsibility |
|--------|----------------|
| `wizard_shell.py` | Footer (`Back` / `Next`), focus areas (`content` / `footer`), global Esc/Ctrl+S routing |
| `meta_form.py` | Meta form mask (4 fields), validation (port int, non-empty strings) |
| `param_grid_list.py` | List renderer, scroll, column layout, readonly filter |
| `param_grid_detail.py` | Detail renderer for one `ParamCell` |
| `param_grid.py` | State machine orchestrating meta → list ⇄ detail; public `run_param_grid` |
| `param_grid_build.py` | `filter_visible_cells()` — tier + readonly |
| `param_grid_plain.py` | Rich two-step fallback |
| `wizards.edit_params` | Pass meta to orchestrator; unchanged call sites |

### State machine

```
                    ┌─────────────┐
                    │  META_FORM  │  (skipped when meta=[])
                    └──────┬──────┘
                           │ Next / Ctrl+S
                           ▼
                    ┌─────────────┐
         ┌─────────│ PARAM_LIST  │─────────┐
         │ Back    └──────┬──────┘         │ Enter (non-bool)
         │ (to meta)      │                ▼
         │                │         ┌─────────────┐
         │                │         │PARAM_DETAIL │
         │                │         └──────┬──────┘
         │                │                │ Enter commit / Esc cancel
         │                ◄────────────────┘
         │                │
         ▼                │ Next / Ctrl+S (save)
       abort              ▼
                    ParamGridResult
```

### Focus ladder

- **Content area:** Up/Down move rows (meta form or param list).
- **← / →** on list rows: move between wizard **pages** only (configuration ↔ parameters). No save or abort on boundary pages.
- **Esc** / footer **Back** / **Ctrl+X**: abort or step back with confirm semantics (Back from meta aborts).
- **Ctrl+S** / footer **Next**: advance or save (Next from params saves).
- **Down on last content row:** focus moves to footer (`Back` selected first).
- **Footer:** Left/Right toggle Back ↔ Next; Enter activates focused button. Buttons left-aligned with list keys.
- **Up from footer:** returns to last content row.

### Shortcuts

| Key | Meta form | Param list | Param detail |
|-----|-----------|------------|--------------|
| Esc | Abort wizard | Back → meta (or abort if no meta) | Cancel edit → list |
| ← / → | Previous / next page (meta ↔ params only) | Previous / next page | — |
| Ctrl+S | Next → params | Save & exit | Commit value → list |
| Enter | Edit focused field / activate footer button | Open detail (non-bool) / footer | Commit value → list |
| Space | — | Toggle bool | Insert space in edit |
| Ctrl+A | — | Toggle advanced tier | — |

Esc while typing in detail: first press clears edit mode; second press returns to list (detail Back), not wizard Back.

### Readonly handling

- `cells_from_specs` still materializes readonly cells with values (bound tokens, etc.).
- `filter_visible_cells(cells, advanced_visible, hide_readonly=True)` excludes `cell.readonly` from list/detail navigation.
- Save uses full `cells` list including readonly keys.

### Layout (list)

- Terminal width from prompt_toolkit `get_app().output.get_size().columns`.
- Three columns: **key**, **value**, **description** (dim, truncated; hints/suggestions detail-only).
- Key and value column widths capped proportionally; description fills remainder.
- Scroll offset keeps focused row visible when row count exceeds content height.

### Layout (detail)

- Title line: param key.
- Description block: word-wrap to `width - 4`.
- Suggestion block: prefixed `Suggestion:`, wrap; omitted if no hint.
- Value line: editable buffer with cursor indicator.

### Plain fallback

1. **Meta step:** Rich table of 4 fields; `B`/`N`/`S`/`X` or labeled commands; all fields shown.
2. **Params step:** Rich table key + value; readonly hidden; row number opens detail prompt showing description + suggestion.

## API

`run_param_grid(cells, meta, *, title, theme)` unchanged signature.

- If `meta` non-empty: show meta form first.
- Returns `ParamGridResult` with `meta` dict and `values` dict.

`edit_params(..., meta=[...])` unchanged for callers.

## Testing

- Unit: `filter_visible_cells` readonly + advanced; column width helper; focus ladder helpers; detail commit validation.
- Unit: TUI builds without error (mocked Application).
- Unit: plain fallback two-step + readonly hidden.
- Full pytest suite green.

## Docs

Update `docs/wizards.md` with list/detail flow, footer navigation, and meta-first config setup.
