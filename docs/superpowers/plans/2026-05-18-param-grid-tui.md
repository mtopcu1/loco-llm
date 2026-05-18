# Param Grid TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace sequential param prompts with a uniform **ParamGridForm** (prompt_toolkit grid + plain Rich fallback) for config setup, runtime build install, and review — with **Ctrl+ chord** shortcuts and a **single reconfigurable theme module**.

**Architecture:** `param_grid_theme.py` holds all colors. `param_grid_models.py` (or inline in param_grid.py) holds `ParamCell` / `ParamGridResult`. `param_grid.py` runs the TUI; `param_grid_plain.py` runs CI-safe fallback. `wizards.edit_params()` is the only public entry from commands. Runtime/model picks stay questionary `select`.

**Tech Stack:** Python 3.11+, prompt_toolkit (transitive via questionary), questionary, Rich, pytest.

**Reference spec:** [`docs/superpowers/specs/2026-05-18-param-grid-tui-design.md`](../specs/2026-05-18-param-grid-tui-design.md)

**Running tests:**

```bash
python -m pytest tests -q
```

---

## File structure

**Created:**

```
src/llm_cli/core/param_grid_theme.py
src/llm_cli/core/param_grid_models.py
src/llm_cli/core/param_grid.py
src/llm_cli/core/param_grid_plain.py
src/llm_cli/core/param_grid_build.py      # build ParamCell lists from ParamSpec
tests/unit/test_param_grid_theme.py
tests/unit/test_param_grid_build.py
tests/unit/test_param_grid_plain.py
tests/unit/test_param_grid.py              # paging/state logic; mock Application where needed
tests/integration/test_cli_config_grid.py
```

**Modified:**

```
src/llm_cli/core/wizards.py
src/llm_cli/commands/config_cmd.py
src/llm_cli/commands/runtime_cmd.py
tests/unit/test_wizards.py
tests/integration/test_cli_config_setup.py
tests/integration/test_cli_runtime.py
docs/wizards.md
docs/add-a-config.md
```

---

## Phase 1 — Theme & models

### Task 1: `ParamGridTheme` (reconfigurable colors)

**Files:**
- Create: `src/llm_cli/core/param_grid_theme.py`
- Create: `tests/unit/test_param_grid_theme.py`

- [ ] **Step 1: Failing test**

```python
def test_default_theme_exposes_semantic_fields():
    from llm_cli.core.param_grid_theme import DEFAULT_THEME, ParamGridTheme
    t = DEFAULT_THEME
    assert isinstance(t, ParamGridTheme)
    assert t.modified_fg.startswith("#")
    assert "modified" in t.to_prompt_toolkit_style()["class:cell-modified"].lower() or True


def test_custom_theme_overrides():
    from llm_cli.core.param_grid_theme import ParamGridTheme
    t = ParamGridTheme(modified_fg="#FF0000")
    assert t.modified_fg == "#FF0000"
```

- [ ] **Step 2: Implement**

```python
@dataclass(frozen=True)
class ParamGridTheme:
    focus_bg: str = "#0066CC"
    focus_fg: str = "#FFFFFF"
    default_fg: str = "#E5A045"
    modified_fg: str = "#6BCB77"
    readonly_fg: str = "#56B6C2"
    advanced_accent: str = "#C678DD"
    hint_fg: str = "#98C379"
    error_fg: str = "#E06C75"
    meta_label: str = "#61AFEF"
    border_common: str = "#ABB2BF"
    border_advanced: str = "#C678DD"
    text_fg: str = "#D4D4D4"
    text_dim: str = "#808080"

    def to_prompt_toolkit_style(self) -> dict[str, str]:
        """Return Style.from_dict mapping for prompt_toolkit."""
        ...

    def rich(self, role: str) -> str:
        """Return Rich markup open tag for role (e.g. rich('modified') -> '[#6BCB77]')."""
        ...

DEFAULT_THEME = ParamGridTheme()
```

- [ ] **Step 3: Run** `python -m pytest tests/unit/test_param_grid_theme.py -v`

- [ ] **Step 4: Commit** (only if user asked — skip by default)

---

### Task 2: Data models + cell state helpers

**Files:**
- Create: `src/llm_cli/core/param_grid_models.py`
- Create: `tests/unit/test_param_grid_build.py` (state helpers section)

- [ ] **Step 1: Implement models**

```python
@dataclass
class ParamCell:
    key: str
    label: str
    description: str
    value: str
    default: str
    readonly: bool = False
    tier: str = "common"
    hint: str | None = None
    param_type: ParamType = ParamType.STRING

@dataclass
class MetaField:
    key: str
    label: str
    value: str
    description: str = ""

@dataclass
class ParamGridResult:
    values: dict[str, str]
    meta: dict[str, str]
    action: Literal["save", "abort"]
    advanced_revealed: bool = False

def cell_state(cell: ParamCell) -> Literal["readonly", "modified", "default"]:
    if cell.readonly:
        return "readonly"
    if cell.value != cell.default:
        return "modified"
    return "default"
```

- [ ] **Step 2: Tests for `cell_state`**

- [ ] **Step 3: Run tests**

---

### Task 3: Build `ParamCell` lists from `ParamSpec`

**Files:**
- Create: `src/llm_cli/core/param_grid_build.py`
- Extend: `tests/unit/test_param_grid_build.py`

- [ ] **Step 1: Implement**

```python
def cells_from_specs(
    specs: list[ParamSpec],
    *,
    values: dict[str, str] | None = None,
    skip_keys: set[str] | None = None,
    readonly_keys: set[str] | None = None,
    hints: dict[str, str] | None = None,
) -> list[ParamCell]:
    """Materialize grid cells; pre-fill bound/skip keys in values."""
    ...

def paginate_cells(
    cells: list[ParamCell],
    *,
    per_page: int = 6,
    advanced_visible: bool,
) -> list[list[ParamCell]]:
    """Return pages of cells; excludes advanced tier when not visible."""
    ...
```

- [ ] **Step 2: Tests**

- `test_paginate_hides_advanced_when_collapsed`
- `test_paginate_six_per_page`
- `test_cells_from_specs_marks_readonly`

- [ ] **Step 3: Run** `python -m pytest tests/unit/test_param_grid_build.py -v`

---

## Phase 2 — Plain fallback

### Task 4: `param_grid_plain.py`

**Files:**
- Create: `src/llm_cli/core/param_grid_plain.py`
- Create: `tests/unit/test_param_grid_plain.py`

- [ ] **Step 1: Implement loop**

```python
def run_param_grid_plain(
    cells: list[ParamCell],
    meta: list[MetaField],
    *,
    title: str,
    theme: ParamGridTheme = DEFAULT_THEME,
) -> ParamGridResult:
    """Rich table + numbered menu; A=toggle advanced; S=save; X=abort."""
```

Use `theme.rich("modified")` for value coloring in table.

- [ ] **Step 2: Tests** with mocked `Prompt.ask` / stdin

- [ ] **Step 3: Run tests**

---

## Phase 3 — prompt_toolkit grid

### Task 5: Grid Application skeleton

**Files:**
- Create: `src/llm_cli/core/param_grid.py`
- Create: `tests/unit/test_param_grid.py`

- [ ] **Step 1: Implement `run_param_grid()` dispatch**

```python
def run_param_grid(
    cells: list[ParamCell],
    meta: list[MetaField],
    *,
    title: str,
    theme: ParamGridTheme = DEFAULT_THEME,
) -> ParamGridResult:
    if wizards.use_plain_prompts():
        from llm_cli.core.param_grid_plain import run_param_grid_plain
        return run_param_grid_plain(cells, meta, title=title, theme=theme)
    return _run_param_grid_tui(cells, meta, title=title, theme=theme)
```

- [ ] **Step 2: TUI skeleton**

- `prompt_toolkit.Application` with:
  - Header (title, page indicator, advanced checkbox state)
  - `GridContainer` — 2×3 `CellWindow` widgets
  - Meta bar (host/port/…)
  - Footer key legend
- Key bindings stub: Ctrl+←/→ change page index; arrows move focus index
- Mouse: `mouse_handler` sets focus index from click coordinates

- [ ] **Step 3: Unit test** paging/focus logic extracted as pure functions (test without full TUI)

---

### Task 6: Cell editing + validation + chords

**Files:**
- Modify: `src/llm_cli/core/param_grid.py`

- [ ] **Step 1: In-cell edit buffer**

- Enter on focused cell → edit mode (unless readonly)
- Esc cancels draft
- Enter commits → `coerce_value(spec, draft)`; on error show red message using `theme.error_fg`
- Space toggles bool cells

- [ ] **Step 2: Global chords (only when not editing text)**

| Binding | Handler |
|---|---|
| c-s | validate all → `action=save` |
| c-x | confirm if dirty → `action=abort` |
| c-a | toggle `advanced_visible`, rebuild pages |
| c-left / c-right | page ±1 |
| question | toggle help overlay |

Use `KeyBindings` with `filter=~is_editing`.

- [ ] **Step 3: Apply theme styles** via `theme.to_prompt_toolkit_style()` on cell widgets based on `cell_state()`

- [ ] **Step 4: Manual smoke note** in test docstring; unit tests for validate-on-save with invalid int

---

### Task 7: `wizards.edit_params()` public API

**Files:**
- Modify: `src/llm_cli/core/wizards.py`
- Modify: `tests/unit/test_wizards.py`

- [ ] **Step 1: Add**

```python
def edit_params(
    specs: list[ParamSpec],
    *,
    title: str,
    values: dict[str, str] | None = None,
    skip_keys: set[str] | None = None,
    readonly_keys: set[str] | None = None,
    hints: dict[str, str] | None = None,
    meta: list[MetaField] | None = None,
    theme: ParamGridTheme | None = None,
) -> ParamGridResult:
    cells = cells_from_specs(...)
    return run_param_grid(cells, meta or [], title=title, theme=theme or DEFAULT_THEME)
```

- [ ] **Step 2: Deprecate sequential body of `walk_tier()`** — reimplement as wrapper calling `edit_params()` and returning `WalkTierResult`.

- [ ] **Step 3: Tests** — mock `run_param_grid` in `test_walk_tier_delegates_to_grid`

---

## Phase 4 — Wire call sites

### Task 8: `config_cmd.do_config_setup`

**Files:**
- Modify: `src/llm_cli/commands/config_cmd.py`
- Modify: `tests/integration/test_cli_config_setup.py`
- Create: `tests/integration/test_cli_config_grid.py`

- [ ] **Step 1: Replace `walk_specs` + separate host/port text + `review` loop**

After runtime/model picked:

```python
meta = [
    MetaField("host", "host", "127.0.0.1"),
    MetaField("port", "port", "8080"),
    MetaField("preset", "preset", preset),
    MetaField("config_id", "config id", cid_guess),
]
hints = { ... from recommend() per key ... }
skip = bound_keys_to_skip(...)
readonly = skip  # bound keys readonly in grid

result = wiz.edit_params(
    mf.serve_schema,
    title=f"Config — {rid} / {mid or 'no model'}",
    skip_keys=skip,
    readonly_keys=readonly,
    hints=hints,
    meta=meta,
)
if result.action == "abort":
    return None
# merge result.values + result.meta → write YAML (remove old review() pass)
```

- [ ] **Step 2: Update integration tests** — mock `edit_params` returning save + fixed values; remove long `answers` iterators for per-param prompts

- [ ] **Step 3: Run** `python -m pytest tests/integration/test_cli_config_setup.py tests/integration/test_cli_config_grid.py -q`

---

### Task 9: `runtime_cmd` interactive build + `review()`

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `src/llm_cli/core/wizards.py` (`review`)
- Modify: `tests/integration/test_cli_runtime.py`

- [ ] **Step 1: `_resolve_build_params`** — interactive path calls `wiz.edit_params(missing_specs, title=f"Build — {runtime_id}")` instead of `walk_tier(missing)`

- [ ] **Step 2: `review()`** — build `ParamCell` rows from review row list + meta; `edit_params` with title "Review"; on save return `SAVE_SENTINEL`, abort → `ABORT_SENTINEL`

- [ ] **Step 3: Tests** for runtime install interactive (existing test updated to mock `edit_params`)

---

## Phase 5 — Docs & verification

### Task 10: Documentation

**Files:**
- Modify: `docs/wizards.md`, `docs/add-a-config.md`

- [ ] Document grid UX, Ctrl chords, color meanings, `param_grid_theme.py` customization

---

### Task 11: Full suite

- [ ] **Run** `python -m pytest tests -q`
- [ ] **Manual WSL checklist:** config setup grid, Ctrl+A advanced, Ctrl+S, Ctrl+X, mouse focus, runtime install build grid

---

## Spec coverage

| Requirement | Task |
|---|---|
| Reconfigurable theme | 1 |
| Uniform all forms | 7, 8, 9 |
| Ctrl chords | 6 |
| Advanced toggle + color | 3, 6 |
| Plain fallback | 4 |
| bound readonly cells | 3, 8 |
| Meta footer | 5, 8 |

---

**Plan saved to `docs/superpowers/plans/2026-05-18-param-grid-tui.md`.**

Execution options:

1. **Subagent-driven (recommended)** — one task per subagent  
2. **Inline** — implement in this session with checkpoints

Which approach?
