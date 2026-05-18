# Wizards & advisor

Release **0.2** adds guided flows alongside existing one-shot commands.

## When to use which

| Goal | Wizard | One-shot |
|---|---|---|
| First-time setup end-to-end | `llm setup` | `llm setup --default` |
| Install or register a runtime | `llm runtime setup` | `llm runtime install <id>` |
| Scaffold a launch config | `llm config setup` | `llm config new --runtime X --model Y --param k=v` |
| VRAM-aware suggestions | `llm advisor` | `llm advisor --runtime X --model Y --json` |

## `llm setup`

Writes machine settings, then offers a Y/n chain: runtime → HF URL → config → background serve. `--default` skips interactive settings prompts and the chain (only prints recommended next steps).

## `llm runtime setup`

- **Preset** — pick an official runtime (`kind: official`); delegates to the same install flow as `llm runtime install`.
- **Custom** — generate `runtimes/<id>/` with `kind: custom`, `params.yaml`, wrapped `serve.sh`, template `healthcheck.sh`, and `.installed` (no build).

Interactive **runtime install / rebuild** steps that collect **build** parameters use the same **param grid** as config setup (not a one-field-at-a-time loop).

## `llm config setup`

Runtime and model picks stay **questionary** selects. Editing is a **two-step wizard**:

1. **Configuration** — host, port, preset, and config id in a compact list (all fields visible). **Enter** opens a detail view for the focused field; **Ctrl+S** or **Next** continues to parameters.
2. **Parameters** — serve params as a compact **key + value + description** list (description truncated; suggestions only in detail). Read-only bound fields (e.g. `bind: model_path` on presets) are **hidden** from the list but still saved. **Enter** opens detail (full description + advisor suggestion + value editor). **Space** toggles booleans in the list. **Ctrl+A** reveals advanced tier.

**Back** (Esc or footer) returns from parameters to configuration, or aborts from the first step. **Next** / **Ctrl+S** on the parameter step validates and writes YAML.

Saving validates types against the runtime schema before writing YAML.

## `llm advisor`

Three forms: interactive (pick runtime + model), `llm advisor <config-id>`, or `--runtime` / `--model`. `--json` prints machine + recommendations. After plain-text output, an optional prompt can open `llm config setup` with the same pair (`--json` suppresses it).

## TUI behavior

**Selections** (runtime, model, menu choices) use **questionary** on a real TTY and fall back to numbered Rich prompts on non-TTY, dumb `TERM`, or when `wizards.force_plain(True)` is in effect.

**Typed parameters** — config serve params, interactive runtime **build** params, and **`review()`** re-edits — use the **param grid** everywhere.

### Param grid shortcuts (TTY)

| Action | Keys |
| --- | --- |
| Next step / save | **Ctrl+S**, or focus **Next** + **Enter** |
| Back / abort step | **Esc**, or focus **Back** + **Enter** |
| Abort entire wizard | **Ctrl+X** |
| Open field detail | **Enter** (on list row) |
| Toggle advanced tier | **Ctrl+A** (parameter list only) |
| Toggle boolean | **Space** (parameter list) |
| Move focus | **↑** / **↓** (last row **↓** → footer buttons) |
| Previous / next wizard step | **←** / **→** (any list row), **Esc** / **Ctrl+S**, or footer **Back** / **Next** |

Also: **Tab** / **Shift+Tab** cycle rows or footer buttons; in detail view type to edit value, **Enter** commits back to list.

### Param grid fallback (plain / CI)

Two steps when meta is present: configuration table (**N** = next), then parameters (**S** = save, **X** = abort, **B** = back to configuration). Row number opens a detail prompt with description and suggestion. **A** toggles advanced tier.

### Param grid colors

Colors encode **meaning**, not decoration:

- **Default** — value still matches the schema default.
- **Modified** — value differs from the default.
- **Read-only** — bound or fixed fields (e.g. `bind: model_path`).
- **Focus** — keyboard/mouse focus highlight.
- **Advanced** accents — headers/borders when the advanced tier is visible.
- **Hint / meta / error** — advisor lines, meta labels, and validation messages.

All palette tokens live in **`src/llm_cli/core/param_grid_theme.py`** (`ParamGridTheme`); adjust that module to re-theme the grid without touching layout code.

## See also

- Spec: [`docs/superpowers/specs/2026-05-18-wizards-and-advisor.md`](superpowers/specs/2026-05-18-wizards-and-advisor.md)
- [`docs/add-a-runtime.md`](add-a-runtime.md)
- Param grid design: [`docs/superpowers/specs/2026-05-18-param-grid-list-detail-design.md`](superpowers/specs/2026-05-18-param-grid-list-detail-design.md)
- [`docs/add-a-recommendation.md`](add-a-recommendation.md)
