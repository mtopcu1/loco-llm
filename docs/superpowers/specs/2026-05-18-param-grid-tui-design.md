# Param grid TUI — design spec

_Date: 2026-05-18_  
_Status: Approved by user — ready for implementation planning_

## 1. Purpose

Replace sequential one-question-at-a-time param prompts with a **uniform, keyboard- and mouse-friendly grid editor** for every wizard that collects typed parameters. Primary pain point: `llm config setup` step 3 after runtime/model selection, with 15+ common and 90+ advanced serve params.

Runtime/model **selection** stays on existing questionary arrow-key lists. **All param editing** (serve, build, review edits) uses the same grid component and visual language.

## 2. Goals

- One **`ParamGridForm`** used everywhere params are walked or reviewed.
- **Grid layout:** label + wrapped description + value per cell; multiple cells per page; **Ctrl+← / Ctrl+→** paging.
- **Advanced:** collapsed by default; **Ctrl+A** toggles advanced pages/section with distinct styling.
- **Cell state colors:** changed vs default vs readonly vs focused vs error.
- **Safe chords:** **Ctrl+S** save/done, **Ctrl+X** abort — no single-key quit while navigating.
- **Mouse:** click cell to focus, then type (standard terminal focus model).
- **Plain fallback** for non-TTY / CI: same data model, Rich table + numbered menu (no mouse).

## 3. Non-goals (v1)

- Textual dependency (use **prompt_toolkit** only for the grid; questionary for pre-step selects).
- Search/filter across 100+ params.
- Animations or alternate-screen “app shell” spanning multiple CLI commands.
- Changing Typer command shapes or JSON output modes.

## 4. User flows

### 4.1 `llm config setup`

1. **Pick runtime** — questionary `select` (unchanged).
2. **Pick model** — questionary `select` (unchanged).
3. **Param grid** — `ParamGridForm` for serve params (common pages; advanced off initially).
4. **Meta footer** — host, port, preset, config id always visible (see §6).
5. **Review** — either merged into same grid (Save via Ctrl+S) or second grid pass with action hints; v1: **single grid session** with Ctrl+S writing after validation, optional confirm on Ctrl+X only.

Bound params (`bind: model_path`): shown **readonly** in grid; not editable.

Advisor hints: shown as subtitle line under description when present (`estimate: …`).

### 4.2 `llm runtime install` / rebuild (interactive build params)

Replace `walk_tier()` sequential `text()` loop with **`ParamGridForm`** over build `ParamSpec` list (same tiers, same advanced toggle).

### 4.3 `review()` and any param re-edit

Replace flat `select("Review — edit row…")` with **`ParamGridForm`** in **review mode**: same cells + **Ctrl+S** = save file / confirm, **Ctrl+X** = abort. No separate menu of `"label    value"` strings.

### 4.4 Other wizards

Any future caller that today uses `walk_tier()` or per-spec `text()` for schema-driven params **must** use `ParamGridForm` instead.

## 5. Architecture

### 5.1 Modules

| Module | Responsibility |
|---|---|
| `src/llm_cli/core/param_grid_theme.py` | Semantic color tokens → prompt_toolkit / Rich |
| `src/llm_cli/core/param_grid.py` | prompt_toolkit `Application`, layout, key bindings, mouse, paging, cell state |
| `src/llm_cli/core/param_grid_plain.py` | Non-TTY renderer + numbered menu loop |
| `src/llm_cli/core/wizards.py` | Thin delegates: `edit_params(...)` → grid or plain based on `use_plain_prompts()` |
| Call sites | `config_cmd.do_config_setup`, `runtime_cmd._resolve_build_params` (interactive), `wizards.review` |

**Import rule:** Only `param_grid.py` imports prompt_toolkit for UI layout (questionary remains for simple selects).

### 5.2 Data model

```python
@dataclass
class ParamCell:
    key: str
    label: str              # display; defaults to key
    description: str
    value: str              # current committed value
    default: str            # schema default as string
    readonly: bool = False
    tier: str = "common"    # common | advanced
    hint: str | None = None # advisor estimate line
    param_type: ParamType   # drives editor: bool toggle, enum select sub-prompt, etc.

@dataclass
class MetaField:
    key: str
    label: str
    value: str
    description: str = ""

@dataclass
class ParamGridResult:
    values: dict[str, str]  # key -> committed string
    meta: dict[str, str]    # host, port, etc.
    action: Literal["save", "abort"]
    advanced_revealed: bool
```

Build from `list[ParamSpec]` + optional `MetaField` list + bound-key injection + recommendations.

### 5.3 Grid geometry

- **Cells per page:** 6 (2 columns × 3 rows) default; configurable constant.
- **Assignment:** schema order; common tier fills pages first; advanced tier fills pages after toggle (page indicator shows section).
- **Pagination:** `Page 2/5 · Common` or `Page 1/12 · Advanced`.

## 6. Layout (TTY)

```
┌─ Config — llamacpp / my-model ────────────────────────────────┐
│  Page 2/4 · Common                    [ ] Advanced  (Ctrl+A)   │
├───────────────────────────────────────────────────────────────┤
│  ┌─ ctx ─────────────┐  ┌─ n_gpu_layers ────┐                 │
│  │ Context window    │  │ GPU layers        │                 │
│  │ 8192              │  │ -1                │                 │
│  └───────────────────┘  └───────────────────┘                 │
│  ...                                                            │
├─ Meta ──────────────────────────────────────────────────────────┤
│  host 127.0.0.1 │ port 8080 │ preset default │ id auto-…       │
├───────────────────────────────────────────────────────────────┤
│ Ctrl+←/→ page │ ↑↓←→ cell │ Enter commit │ Ctrl+A adv        │
│ Ctrl+S save │ Ctrl+X abort │ ? help                          │
└───────────────────────────────────────────────────────────────┘
```

- **Meta bar:** always visible; Tab or click to edit meta fields (inline, same commit rules).
- **Advanced off:** advanced cells not in page list; footer shows `Advanced hidden (N params)`.
- **Advanced on:** advanced pages appended; section label and border use **Advanced palette** (§7).

## 7. Color & style system

**Reconfiguration:** all colors live in a single module `src/llm_cli/core/param_grid_theme.py` as named semantic tokens (no inline hex/scheme strings in layout code). Swap palette by editing that file only (future: optional env `LLM_TUI_THEME=` or YAML — out of scope for v1).

```python
@dataclass(frozen=True)
class ParamGridTheme:
    focus_bg: str = "#0066CC"
    default_fg: str = "#E5A045"      # unchanged from schema default
    modified_fg: str = "#6BCB77"
    readonly_fg: str = "#56B6C2"
    advanced_accent: str = "#C678DD"
    hint_fg: str = "#98C379"
    error_fg: str = "#E06C75"
    meta_label: str = "#61AFEF"
    border_common: str = "#ABB2BF"
    border_advanced: str = "#C678DD"
```

`param_grid.py` calls `theme.to_prompt_toolkit_style()`; `param_grid_plain.py` calls `theme.to_rich_markup(name)`.

Use prompt_toolkit `Style` names (mapped to Rich-like semantic colors). Consistent across all forms.

| Semantic | Theme field | When |
|---|---|---|
| **Focus** | `focus_bg` + bold | Keyboard/mouse focused cell |
| **Default** | `default_fg` | Committed value equals schema default |
| **Modified** | `modified_fg` | User changed value from default |
| **Readonly** | `readonly_fg` | Bound `${model_path}` or system-derived |
| **Advanced section** | `advanced_accent` | Advanced pages / toggle on |
| **Common section** | `border_common` | Common pages |
| **Hint** | `hint_fg` | Advisor estimate line |
| **Error** | `error_fg` | Invalid draft on commit |
| **Meta bar** | `meta_label` | host/port/preset/id labels |

**Legend (optional F1 overlay):** small key explaining colors.

Bool cells: show `[x]` / `[ ]`; Space toggles while focused (Enter also commits).

Enum cells: Enter opens questionary sub-`select` overlay (modal on top of grid) or inline cycle if ≤4 values.

## 8. Key bindings

Global chords only when **not** in raw text-edit mode for a cell (except Enter/Esc in editor).

| Binding | Action |
|---|---|
| ↑ ↓ ← → | Move focus between cells on page |
| Tab / Shift+Tab | Next/previous cell (wrap) |
| **Ctrl+→** / **Ctrl+←** | Next/previous page |
| **Ctrl+A** | Toggle advanced section |
| **Enter** | Start edit (if not editing) or commit cell (if editing) |
| **Esc** | Cancel in-cell edit; restore draft to last committed |
| **Ctrl+Z** | Reset focused cell to schema default |
| **Ctrl+S** | Validate all → `action=save` |
| **Ctrl+X** | If dirty → confirm; else `action=abort` |
| **?** or **F1** | Toggle help overlay |

**No single-key s/q/d** for save/abort/quit.

Mouse: click cell → focus; double-click optional → enter edit mode (v1: single click + type enters edit).

## 9. Validation & save

- On **Ctrl+S**: run `coerce_value` + `validate_params` for all keys; errors highlight first bad cell (red) and block save.
- Config path: merge meta + params → existing YAML write / review callback.
- Runtime install: merge into build params dict → existing install flow.

## 10. Plain fallback (`param_grid_plain.py`)

When `use_plain_prompts()`:

1. Print Rich **Table** of cells (key, description, value, state color via markup).
2. Numbered menu: `[1-N]` edit param, `[A]` toggle advanced, `[S]` save, `[X]` abort.
3. Same `ParamCell` list and validation on save.

Tests use `force_plain(True)` and stdin mocks (existing pattern).

## 11. Chaining (`llm setup`)

Each grid session is a **modal** `Application.run()` that **must** restore terminal on exit (success, abort, or exception). Sequence:

`questionary selects` → `ParamGridForm` (runtime build) → … → `questionary`/prompt URL → `ParamGridForm` (config) → serve.

No nested Applications; sub-prompts (enum) exit before returning to grid.

## 12. Testing

- Unit: page slicing, state color resolution (default/modified/readonly), advanced toggle filters pages.
- Unit: plain renderer menu loop with mocked stdin.
- Integration: `config setup` with monkeypatched grid returning fixed values; assert no sequential `text()` per param.
- Manual: WSL real TTY — mouse click, Ctrl+S/X, advanced toggle, 100+ param paging.

## 13. Documentation

- Update `docs/wizards.md` — grid UX, shortcuts, colors, plain fallback.
- Update `docs/add-a-config.md` — config setup step 3 description.

## 14. Success criteria

- [ ] All param walks use `ParamGridForm` (config serve, runtime build interactive, review).
- [ ] Config setup: common params on paginated grid; advanced hidden until Ctrl+A.
- [ ] Modified vs default cells visually distinct (green vs orange).
- [ ] Advanced section visually distinct (magenta accent).
- [ ] Ctrl+S / Ctrl+X only for save/abort; no accidental single-key quit.
- [ ] Readonly bound params visible, not editable.
- [ ] Plain fallback passes CI tests.
- [ ] Full pytest green.

## 15. References

- [`2026-05-18-llamacpp-vllm-runtime-params-design.md`](2026-05-18-llamacpp-vllm-runtime-params-design.md) — bind model_path, exhaustive params
- [`2026-05-18-wizards-and-advisor.md`](2026-05-18-wizards-and-advisor.md) — questionary hybrid baseline
- `src/llm_cli/core/wizards.py`, `src/llm_cli/commands/config_cmd.py`
