# Serve / Build Param Opt-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optional runtime serve/build params are opt-in only — disabled rows are omitted from YAML and env; schema `default` is removed from catalogs; Space toggles enable in the param grid (serve + build).

**Architecture:** Extend `ParamCell` with `enabled` + `locked` flags; `cells_from_specs` starts optional rows disabled and empty; save path filters to enabled rows with valid values; `validate_params` validates only supplied keys + required; runtime install uses the same `edit_params` grid as config setup (retire `walk_tier` fill behavior). Catalogs drop all `default:` keys; `parse_schema` rejects `default` if present.

**Tech Stack:** Python 3.11+, Typer, prompt-toolkit param grid, PyYAML runtime catalogs, pytest.

**Related spec:** `docs/superpowers/specs/2026-05-19-serve-build-param-opt-in-design.md`

**Implementation branch:** create `feat/serve-build-param-opt-in` from `main` before Task 1 (see git-workflow rule — never commit on `main`).

---

## Background — what exists today

- **Param schema:** `runtimes/<id>/params.yaml` parsed by `parse_schema()` in `src/llm_cli/core/params.py` into `ParamSpec` objects (includes optional `default`).
- **Validation:** `validate_params()` coerces supplied keys and **back-fills** any missing key that has `spec.default`.
- **Config setup:** `config_cmd.do_config_setup()` → `wizards.edit_params()` → `cells_from_specs()` pre-fills schema defaults → saves **all** cell values to `serve.params`.
- **Runtime install:** `_resolve_build_params()` uses `walk_tier()` to prompt/fill missing build params, then `validate_params()` (defaults again).
- **Serve:** `_serve_env_from_params()` in `serve.py` sets env vars only for keys in the coerced map (already correct once upstream stops stuffing defaults).
- **Grid UX:** Space toggles **bool** values in list view (`param_grid.py::_toggle_bool_at`).

## File map

**Create:**
- `tests/unit/test_param_grid_save.py` — save-filter / enabled-values helpers

**Modify (core):**
- `src/llm_cli/core/params.py` — remove `default` from `ParamSpec`; reject in `parse_schema`; stop default fill in `validate_params`
- `src/llm_cli/core/param_grid_models.py` — `enabled`, `locked`; new `cell_state` literals
- `src/llm_cli/core/param_grid_build.py` — opt-in cell init; add `enabled_values_from_cells()`
- `src/llm_cli/core/param_grid.py` — Space → toggle enable; suggestion column; save validation
- `src/llm_cli/core/param_grid_layout.py` — indicator + suggestion columns
- `src/llm_cli/core/param_grid_theme.py` — styles for disabled / enabled-empty / enabled-set / locked
- `src/llm_cli/core/param_grid_plain.py` — plain fallback parity
- `src/llm_cli/core/wizards.py` — export save helper usage; mark `walk_tier` deprecated

**Modify (commands):**
- `src/llm_cli/commands/config_cmd.py` — save filtered params
- `src/llm_cli/commands/runtime_cmd.py` — build install via `edit_params` grid

**Modify (catalogs):**
- `runtimes/llamacpp/params.yaml` — strip all `default:` lines
- `runtimes/vllm/params.yaml` — strip all `default:` lines
- `runtime_cmd.py` `_CUSTOM_PARAMS_YAML` if it contains defaults

**Modify (tests):** `test_params.py`, `test_param_grid*.py`, `test_wizards.py`, `test_registry.py`, `test_serve_env.py`, `test_cli_runtime.py`, `test_cli_config_setup.py`, `test_cli_config_new.py`, `tests/tui/seed.py`, TUI tests as needed

**Modify (docs):**
- `docs/add-a-runtime.md`, `docs/wizards.md`, `docs/add-a-config.md`

**Untouched:**
- `serve.sh` / `_serve_flags.sh` (already skip empty env)
- `recommend()` / advisor (hints only; no catalog fallback)

---

## Task 1: Param schema — remove `default`, strict `parse_schema`

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Replace default-fill test with reject-default test**

In `tests/unit/test_params.py`, remove `test_validate_params_fills_defaults` and add:

```python
def test_parse_schema_rejects_default_key():
    with pytest.raises(ValueError, match="default.*removed"):
        parse_schema({"ctx": {"type": "int", "default": 8192}})


def test_validate_params_does_not_fill_missing_optional():
    specs = parse_schema({"ctx": {"type": "int"}, "host": {"type": "string", "required": True}})
    out, errors = validate_params(specs, {})
    assert errors == []
    assert out == {}  # no back-fill


def test_validate_params_required_still_errors_when_missing():
    specs = parse_schema({"name": {"type": "string", "required": True}})
    out, errors = validate_params(specs, {})
    assert out == {}
    assert any("required" in e for e in errors)
```

Update `test_parse_schema_basic_types` to omit `default` keys from raw dict and remove assertions on `.default`.

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/unit/test_params.py -q
```

- [ ] **Step 3: Implement in `params.py`**

1. Remove `default: Any = None` from `ParamSpec` dataclass.
2. In `parse_schema`, after reading entry dict:

```python
if "default" in entry:
    raise ValueError(
        f"param {key!r}: `default` was removed from params.yaml; "
        "use loco advisor for suggestions"
    )
```

3. Remove `default=entry.get("default")` from `ParamSpec(...)` construction.
4. In `validate_params`, delete the branch:

```python
elif spec.default is not None:
    coerced[spec.key] = spec.default
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/unit/test_params.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "refactor(params): remove catalog default fill and reject default key"
```

---

## Task 2: ParamCell enabled/locked + cell_state

**Files:**
- Modify: `src/llm_cli/core/param_grid_models.py`
- Modify: `tests/unit/test_param_grid_build.py`

- [ ] **Step 1: Add failing tests**

Replace `test_cell_state_default` / `test_cell_state_modified` with:

```python
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
        key="k", label="l", description="", value="x", enabled=True, locked=True, readonly=True
    )
    assert cell_state(c) == "locked"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/unit/test_param_grid_build.py::test_cell_state_disabled -q
```

- [ ] **Step 3: Update `param_grid_models.py`**

```python
@dataclass
class ParamCell:
    key: str
    label: str
    description: str
    value: str
    enabled: bool = False
    locked: bool = False
    readonly: bool = False
    tier: str = "common"
    hint: str | None = None
    param_type: ParamType = ParamType.STRING


def cell_state(cell: ParamCell) -> Literal["locked", "disabled", "enabled-empty", "enabled-set"]:
    if cell.locked or cell.readonly:
        return "locked"
    if not cell.enabled:
        return "disabled"
    if not str(cell.value).strip() and cell.param_type is not ParamType.BOOL:
        return "enabled-empty"
    return "enabled-set"
```

Remove the old `default` field from `ParamCell`.

- [ ] **Step 4: Fix compile errors** — grep for `.default` on `ParamCell` in tests and update call sites (Tasks 3–6 will finish grid files).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(param-grid): add enabled and locked flags to ParamCell"
```

---

## Task 3: `cells_from_specs` opt-in initialization

**Files:**
- Modify: `src/llm_cli/core/param_grid_build.py`
- Modify: `tests/unit/test_param_grid_build.py`

- [ ] **Step 1: Add failing tests**

```python
def test_cells_from_specs_optional_starts_disabled_empty() -> None:
    specs = [ParamSpec("ctx", ParamType.INT), ParamSpec("name", ParamType.STRING, required=True)]
    cells = cells_from_specs(specs)
    by = {c.key: c for c in cells}
    assert by["ctx"].enabled is False
    assert by["ctx"].value == ""
    assert by["name"].enabled is True
    assert by["name"].locked is True


def test_cells_from_specs_explicit_value_enables_key() -> None:
    specs = [ParamSpec("ctx", ParamType.INT)]
    cells = cells_from_specs(specs, values={"ctx": "8192"})
    c = cells[0]
    assert c.enabled is True
    assert c.value == "8192"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Rewrite `cells_from_specs`**

```python
def cells_from_specs(
    specs: list[ParamSpec],
    *,
    values: dict[str, str] | None = None,
    skip_keys: set[str] | None = None,
    readonly_keys: set[str] | None = None,
    hints: dict[str, str] | None = None,
) -> list[ParamCell]:
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
```

- [ ] **Step 4: Run build tests**

```bash
python -m pytest tests/unit/test_param_grid_build.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(param-grid): initialize optional params disabled without catalog defaults"
```

---

## Task 4: Save filter — `enabled_values_from_cells`

**Files:**
- Modify: `src/llm_cli/core/param_grid_build.py`
- Create: `tests/unit/test_param_grid_save.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_param_grid_save.py`:

```python
from __future__ import annotations

import pytest

from llm_cli.core.param_grid_build import enabled_values_from_cells
from llm_cli.core.param_grid_models import ParamCell
from llm_cli.core.params import ParamSpec, ParamType, ParamValidationError


def _cell(key: str, *, enabled: bool, value: str, locked: bool = False, ptype=ParamType.INT):
    return ParamCell(
        key=key, label=key, description="", value=value,
        enabled=enabled, locked=locked, param_type=ptype,
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
```

- [ ] **Step 2: Run — expect FAIL (import error)**

- [ ] **Step 3: Implement in `param_grid_build.py`**

```python
def enabled_values_from_cells(
    cells: list[ParamCell],
    specs: list[ParamSpec],
) -> dict[str, str]:
    """Return param map for YAML/env: enabled + locked rows only; validate non-empty."""
    spec_by_key = {s.key: s for s in specs}
    out: dict[str, str] = {}
    for cell in cells:
        if not (cell.enabled or cell.locked):
            continue
        if cell.param_type is not ParamType.BOOL and not str(cell.value).strip():
            raise ParamValidationError(
                f"param {cell.key!r}: enabled but empty; set a value or disable"
            )
        out[cell.key] = cell.value
    for spec in specs:
        if spec.required and spec.key not in out:
            raise ParamValidationError(f"param {spec.key!r}: required")
    # drop unknown keys guard handled by validate_params later
    return out
```

- [ ] **Step 4: Run tests — PASS**

```bash
python -m pytest tests/unit/test_param_grid_save.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(param-grid): filter enabled param values on save"
```

---

## Task 5: TUI grid — Space toggles enable, remove list bool toggle

**Files:**
- Modify: `src/llm_cli/core/param_grid.py`
- Modify: `src/llm_cli/core/param_grid_layout.py`
- Modify: `src/llm_cli/core/param_grid_theme.py`
- Modify: `tests/unit/test_param_grid.py`

- [ ] **Step 1: Update theme** — add style keys: `cell-disabled`, `cell-enabled-empty`, `cell-enabled-set`, `cell-locked`; map in `style_for_cell_state()`.

- [ ] **Step 2: Update layout** — list rows render four columns: indicator (`[ ]`/`[x]`/`[•]`), key, value, suggestion (from `cell.hint`, truncated).

- [ ] **Step 3: Replace `_toggle_bool_at` with `_toggle_enable_at`**

```python
def _toggle_enable_at(index: int) -> None:
    visible = _visible_param_cells()
    if index < 0 or index >= len(visible):
        return
    cell = visible[index]
    if cell.locked or cell.readonly:
        return
    cell.enabled = not cell.enabled
    if not cell.enabled:
        cell.value = ""
```

Wire Space key to `_toggle_enable_at` only (remove bool branch).

- [ ] **Step 4: Update `_exit_save`**

```python
from llm_cli.core.param_grid_build import enabled_values_from_cells

def _exit_save() -> None:
    try:
        filtered = enabled_values_from_cells(cells, [_spec_for_cell(c) for c in cells])
    except ParamValidationError as exc:
        _set_error(str(exc))
        return
    for cell in cells:
        try:
            if cell.enabled or cell.locked:
                _coerce_and_format(cell, cell.value)
        except ParamValidationError as exc:
            _set_error(f"{cell.key}: {exc}")
            return
    app.exit(result=ParamGridResult(values=filtered, meta=..., action="save", ...))
```

Pass full `specs` list into `run_param_grid` if not already available (add parameter from `edit_params`).

- [ ] **Step 5: Unit test** — mock grid state: Space on disabled row → enabled toggles; bool not flipped in list.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(param-grid): space toggles enable; show suggestion column"
```

---

## Task 6: Plain fallback parity

**Files:**
- Modify: `src/llm_cli/core/param_grid_plain.py`
- Modify: `tests/unit/test_param_grid_plain.py`

- [ ] **Step 1: Update plain list** — show `[ ] key = (off)` / `[x] key = value`; `[S]` toggle enable by row number; detail prompt for value when enabling.

- [ ] **Step 2: Save uses `enabled_values_from_cells`** same as TUI.

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/unit/test_param_grid_plain.py -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(param-grid): plain fallback opt-in param semantics"
```

---

## Task 7: Config commands — save filtered params

**Files:**
- Modify: `src/llm_cli/commands/config_cmd.py`
- Modify: `tests/integration/test_cli_config_new.py`

- [ ] **Step 1: Update `do_config_setup`**

After `result.action == "save"`, `result.values` is already filtered by grid. Keep:

```python
params_final = apply_model_bindings(mf.serve_schema, dict(result.values), model_id=mid)
coerced, errors = validate_params(mf.serve_schema, params_final)
```

- [ ] **Step 2: Update `do_config_new`** — `--param k=v` pre-enables keys (pass as `values=` to grid if interactive; for non-interactive, pass raw dict only containing explicit flags — no default fill).

- [ ] **Step 3: Integration test** — mock `edit_params` returning sparse values:

```python
def test_config_setup_saves_only_enabled_params(monkeypatch, tmp_path):
    monkeypatch.setattr(wizards, "edit_params", lambda *a, **k: ParamGridResult(
        values={"ctx": "8192"},  # only one key
        meta={"host": "127.0.0.1", "port": "8080", "preset": "default", "config_id": "x"},
        action="save",
    ))
    # invoke config setup; assert written YAML serve.params == {"ctx": 8192} (+ bound keys)
```

- [ ] **Step 4: Run targeted tests**

```bash
python -m pytest tests/integration/test_cli_config_setup.py tests/integration/test_cli_config_new.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(config): save opt-in serve params only"
```

---

## Task 8: Runtime install — grid instead of `walk_tier`

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime.py`
- Modify: `tests/unit/test_wizards.py`

- [ ] **Step 1: Replace interactive branch in `_resolve_build_params`**

When not `yes` and schema non-empty:

```python
from llm_cli.core import wizards as wiz

pre_values = {k: str(v) for k, v in raw.items()}
result = wiz.edit_params(
    schema,
    title=f"Build params: {runtime_id}",
    values=pre_values,
)
if result.action == "abort":
    raise typer.Exit(code=1)
raw.update(result.values)
```

Remove `walk_tier(missing)` call.

- [ ] **Step 2: `--yes` path** — only CLI `--param` flags + required; no grid; no default fill.

- [ ] **Step 3: Update tests** — replace `@patch walk_tier` tests with `@patch edit_params`; assert sparse `build_params` in `.installed`.

- [ ] **Step 4: Run**

```bash
python -m pytest tests/integration/test_cli_runtime.py tests/unit/test_wizards.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(runtime): build install uses opt-in param grid"
```

---

## Task 9: Strip `default:` from runtime catalogs

**Files:**
- Modify: `runtimes/llamacpp/params.yaml`
- Modify: `runtimes/vllm/params.yaml`
- Modify: fixture YAML in tests (`tests/tui/seed.py`, `test_registry.py`, etc.)

- [ ] **Step 1: Remove defaults from catalogs**

```bash
python - <<'PY'
from pathlib import Path
import re
for path in [Path("runtimes/llamacpp/params.yaml"), Path("runtimes/vllm/params.yaml")]:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^  default: .*\n", "", text, flags=re.M)
    path.write_text(text, encoding="utf-8")
PY
```

- [ ] **Step 2: Grep tests/fixtures for `default:` in params snippets and remove.

```bash
rg "default:" runtimes tests --glob "*.yaml" --glob "*.py"
```

- [ ] **Step 3: Run registry + manifest tests**

```bash
python -m pytest tests/unit/test_registry.py tests/unit/test_release_config.py -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(runtimes): remove default keys from param catalogs"
```

---

## Task 10: Fix remaining tests + doctor defaults

**Files:**
- Modify: `src/llm_cli/core/doctor.py` (`_default_build_params` — return `{}` or required-only, not default fill)
- Modify: `tests/unit/test_doctor_runtime_scope.py`, `tests/integration/test_cli_doctor.py`
- Any other failing tests from full suite

- [ ] **Step 1: Run full suite, collect failures**

```bash
python -m pytest -q
```

- [ ] **Step 2: Fix `_default_build_params`** in `doctor.py`:

```python
def _default_build_params(mf: RuntimeManifest) -> dict[str, Any]:
    return {}  # doctor checks requirements with empty build params unless installed
```

Adjust tests that expected cuda default from manifest.

- [ ] **Step 3: Re-run until green**

```bash
python -m pytest -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "test: align suite with opt-in param semantics"
```

---

## Task 11: Documentation

**Files:**
- Modify: `docs/add-a-runtime.md`, `docs/wizards.md`, `docs/add-a-config.md`

- [ ] **Step 1: Update `add-a-runtime.md`** — remove "default — used when omitted"; document opt-in, `required`, advisor suggestions.

- [ ] **Step 2: Update `wizards.md`** — Space enables param; bools in detail; suggestions column; breaking note to recreate configs.

- [ ] **Step 3: Update `add-a-config.md`** — `serve.params` contains only enabled keys.

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: document opt-in serve and build params"
```

---

## Task 12: Final verification + PR

- [ ] **Step 1: Full pytest**

```bash
python -m pytest -q
```

Expected: all pass (TUI pexpect tests may skip on Windows).

- [ ] **Step 2: Manual smoke (Linux/WSL if available)**

```bash
loco config setup --runtime stub-runtime   # enable one param only; verify YAML size
loco config show <id>                       # sparse serve.params
```

- [ ] **Step 3: Open PR**

Title: `feat!: opt-in serve and build params; remove catalog defaults`

Body: link spec; note breaking change — recreate configs; `default` removed from params.yaml.

- [ ] **Step 4: After merge** — release-please release PR → tag; users recreate configs.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Opt-in shipping | 3, 4, 7, 8 |
| Unified serve + build grid | 5, 6, 8 |
| Space enable, no list bool toggle | 5 |
| Required/bound locked | 2, 3 |
| Remove catalog `default` | 1, 9 |
| Reject `default` in parse | 1 |
| Advisor suggestions in UI | 5 (hint column) |
| No migration | docs only |
| `validate_params` no fill | 1 |
| Breaking `feat!:` | Task 12 PR title |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-serve-build-param-opt-in.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with executing-plans checkpoints

Which approach?
