# Web Dashboard Param Grid & New-Config Wizard (Plan 3/5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw-JSON config editor that landed in Plan 2 with a first-class React param grid (the dashboard's flagship form). Add a 5-step new-config wizard that walks the user through runtime → model → params (with advisor hints) → review → save. The param grid is the single hardest component in the entire dashboard project; getting it right is what makes the dashboard feel like a peer to the CLI rather than a stripped-down web view.

**Architecture:** Two new backend endpoints surface the data: `/api/runtimes/{id}/default-params` (the `ParamCell[]` shape for a fresh config) and `/api/recommendations` (advisor hints, queryable by runtime+model). Both reuse `core/param_grid_models.py` and `core/recommendations.py` directly — no new business logic, just REST surfaces. React grows: a shared `<ParamGrid>` component drives both the config-detail Params tab (replacing read-only JSON dump) and the wizard's step 3.

**Tech Stack:** Unchanged from Plans 1–2. Adds no new dependencies — `ParamCell` is plain JSON, the grid is shadcn `Table` + `Input` + `Checkbox`.

**Related spec:** `docs/superpowers/specs/2026-05-20-web-dashboard-design.md` (§8.7 Param grid component, §8.9 Configs wizard)

**Previous plans (must be merged first):** Plans 1 and 2.

**Subsequent plans:**
- Plan 4 — Live metrics pipeline
- Plan 5 — Security hardening + update notifier + perf budgets + CI polish

**Implementation branch:** `feat/web-dashboard-param-grid` from `main` after Plan 2 merges.

---

## Background — what Plans 1+2 landed

- Plan 1: `/api/configs/{id}/params` returns the `ParamCell[]` shape produced by `core/param_grid_models.py` (the same shape the TUI consumes). UI renders this as a read-only JSON `<pre>`.
- Plan 1: `/api/configs/{id}/validate` returns `{valid, errors}`.
- Plan 2: `ConfigForm` is a single-textarea JSON editor over `serve.params`; `NewConfigPage` mounts it in create mode; `POST/PUT/DELETE /api/configs` all live.

This plan **adds** a real `ParamCell`-aware UI and an advisor-aware wizard. The Plan 2 raw-form path stays as a fallback (accessible from Raw YAML tab) — useful when something goes wrong with the grid, and a stable reference when the grid's behavior is questioned.

---

## Cross-plan invariants (from Plan 2, still hold)

- **ParamCell is the contract** between TUI, REST, and React. Don't define separate shapes per surface.
- **Recommendations come from `core/recommendations.py`.** Don't reinvent advisor logic client-side.
- **TanStack Query keys:** `['configs', id, 'params']`, `['runtimes', id, 'default-params']`, `['recommendations', runtimeId, modelId]`.
- **No new ErrorCode values** — wizard validation surfaces existing `CONFIG_INVALID` from Plan 2.

---

## File map

**Create (Python):**
- `tests/webapi/test_routes_recommendations.py`
- `tests/webapi/test_routes_default_params.py`

**Create (React):**
- `dashboard/src/features/params/ParamGrid.tsx` — the flagship component
- `dashboard/src/features/params/ParamRow.tsx` — single row (extracted for readability + testability)
- `dashboard/src/features/params/ParamValueInput.tsx` — type-aware value input dispatcher
- `dashboard/src/features/params/useParamGridState.ts` — local state machine (enabled/value edits, filter, save buffer)
- `dashboard/src/features/params/__tests__/ParamGrid.test.tsx`
- `dashboard/src/features/configs/wizard/NewConfigWizard.tsx`
- `dashboard/src/features/configs/wizard/StepPickRuntime.tsx`
- `dashboard/src/features/configs/wizard/StepPickModel.tsx`
- `dashboard/src/features/configs/wizard/StepParams.tsx`
- `dashboard/src/features/configs/wizard/StepReview.tsx`
- `dashboard/src/features/configs/wizard/StepSave.tsx`
- `dashboard/src/features/configs/wizard/__tests__/NewConfigWizard.test.tsx`
- `dashboard/src/lib/paramCell.ts` — pure functions over `ParamCell[]` (filter, apply-suggestion, etc.) — shared between grid + wizard

**Modify (Python):**
- `src/llm_cli/webapi/routes/configs.py` — confirm `/api/configs/{id}/params` is complete (Plan 1) + add `/api/runtimes/{id}/default-params` (delegates to `core/param_grid_models.load_defaults_for_runtime(runtime_id, model_id?)`)
- `src/llm_cli/webapi/routes/__init__.py` (or `webapi/app.py`) — register a new `recommendations` router
- `src/llm_cli/webapi/routes/recommendations.py` — new file: `GET /api/recommendations?runtime_id=...&model_id=...`
- `src/llm_cli/core/param_grid_models.py` — if `load_defaults_for_runtime(...)` doesn't exist, add it (mirror `load_for(config_id)` but feed defaults, not stored values)
- `src/llm_cli/core/recommendations.py` — ensure `compute(runtime_id, model_id) -> list[Recommendation]` is callable from REST (add a small wrapper if the existing entry point requires TUI context)

**Modify (React):**
- `dashboard/src/features/configs/ConfigDetailPage.tsx` — Params tab swaps `<ParamsView>` (the Plan 1 JSON dump) for `<ParamGrid mode="edit" configId={id} />`
- `dashboard/src/features/configs/ConfigForm.tsx` — remains as the Raw YAML editor; the new wizard is the default creation path
- `dashboard/src/features/configs/NewConfigPage.tsx` — replaces its body with `<NewConfigWizard />`
- `dashboard/src/router.tsx` — `/configs/new` still routes to `NewConfigPage`, but it's now the wizard
- `dashboard/src/test/handlers.ts` — add handlers for `/api/recommendations`, `/api/runtimes/{id}/default-params`

**Untouched:**
- TUI param grid (`core/param_grid.py`, `core/param_grid_layout.py`, etc.) — only consumed; never modified
- Live metrics (Plan 4)
- Security hardening (Plan 5)

---

## Task 1: Backend — `/api/runtimes/{id}/default-params`

**Files:**
- Modify: `src/llm_cli/webapi/routes/configs.py` (or a new `routes/runtimes_params.py` — your call; the spec puts it on the runtimes path)
- Modify: `src/llm_cli/core/param_grid_models.py` (if needed)
- Create: `tests/webapi/test_routes_default_params.py`

**Endpoint:** `GET /api/runtimes/{id}/default-params?model_id={optional}` → `list[ParamCell]`.

Behavior: return the default cells for a fresh config — all optional params disabled, required params with locked defaults from the schema, no overrides yet. If `model_id` is given, pre-populate any params whose default depends on the model (e.g., `gguf_path` for llamacpp).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.webapi
def test_default_params_for_stub_runtime(test_client):
    r = test_client.get("/api/runtimes/stub-runtime/default-params", headers={"Host": "testserver"})
    assert r.status_code == 200
    cells = r.json()
    assert isinstance(cells, list)
    keys = {c["key"] for c in cells}
    # stub-runtime has these params (adapt to actual schema):
    assert "host" in keys


@pytest.mark.webapi
def test_default_params_with_model_populates_model_path(test_client, seed_model):
    seed_model("qwen2-7b", format="gguf")
    r = test_client.get(
        "/api/runtimes/llamacpp/default-params?model_id=qwen2-7b",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    cells = r.json()
    gguf = next((c for c in cells if c["key"] == "gguf_path"), None)
    assert gguf is not None
    assert "qwen2-7b" in str(gguf["value"])
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement the route**

```python
@router.get("/runtimes/{runtime_id}/default-params")
def default_params(runtime_id: str, model_id: str | None = None):
    from llm_cli.core import param_grid_models as pgm
    from llm_cli.core import registry
    try:
        registry.get_runtime(runtime_id)
    except KeyError:
        raise ApiError(ErrorCode.RUNTIME_NOT_FOUND, "...", status_code=404)
    cells = pgm.load_defaults_for_runtime(runtime_id, model_id=model_id)
    return [c.as_dict() for c in cells]
```

If `load_defaults_for_runtime(runtime_id, model_id)` doesn't exist in `param_grid_models.py`, add it — it should mirror `load_for(config_id)` but seed from `{}` instead of stored `serve.params`, and apply model-derived defaults (look at how the existing TUI populates these — there's already code for it in `core/wizards.py` or `core/scaffold.py`; extract).

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webapi): GET /api/runtimes/{id}/default-params for the new-config wizard"
```

---

## Task 2: Backend — `/api/recommendations`

**Files:**
- Create: `src/llm_cli/webapi/routes/recommendations.py`
- Modify: `src/llm_cli/webapi/app.py`
- Modify: `src/llm_cli/core/recommendations.py` (if needed)
- Create: `tests/webapi/test_routes_recommendations.py`

**Endpoint:** `GET /api/recommendations?runtime_id=&model_id=` → `list[Recommendation]` where each is `{param_key, suggested_value, reason, confidence}`.

- [ ] **Step 1: Tests**

```python
@pytest.mark.webapi
def test_recommendations_for_runtime_model(test_client, seed_model):
    seed_model("qwen2-7b", format="gguf")
    r = test_client.get(
        "/api/recommendations?runtime_id=llamacpp&model_id=qwen2-7b",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    recs = r.json()
    assert isinstance(recs, list)
    # No assertion on specific recs — runtime-dependent — just shape.
    for rec in recs:
        assert {"param_key", "suggested_value", "reason"} <= set(rec)
```

- [ ] **Step 2: Implement**

```python
from fastapi import APIRouter

from llm_cli.core import recommendations as rec_module

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations")
def recommendations(runtime_id: str, model_id: str | None = None):
    recs = rec_module.compute(runtime_id=runtime_id, model_id=model_id)
    return [r.as_dict() if hasattr(r, "as_dict") else r for r in recs]
```

If `recommendations.compute(...)` signature differs, adapt or add a thin REST-friendly wrapper. Goal: every advisor hint the TUI shows must be reachable via this endpoint, identically computed.

- [ ] **Step 3: Register router in `webapi/app.py`**

```python
from llm_cli.webapi.routes import recommendations as rec_routes
api.include_router(rec_routes.router)
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webapi): GET /api/recommendations (advisor hints by runtime+model)"
```

---

## Task 3: Regenerate the TypeScript API client

```bash
scripts/regen-api-client.sh
scripts/regen-api-client.sh --check
git add dashboard/src/api/generated.ts
git commit -m "chore(dashboard): regen API client for Plan 3 endpoints"
```

---

## Task 4: Shared param utilities (`lib/paramCell.ts`)

**Files:**
- Create: `dashboard/src/lib/paramCell.ts`
- Create: `dashboard/src/lib/__tests__/paramCell.test.ts`

Pure-functional helpers. No React, no I/O — testable in isolation.

```ts
import type { paths } from '@/api/generated'

// Pull the ParamCell type out of the OpenAPI schema; adjust path if codegen
// places it differently.
export type ParamCell = NonNullable<
  paths['/configs/{id}/params']['get']['responses']['200']['content']['application/json']
>[number]

export interface Recommendation {
  param_key: string
  suggested_value: unknown
  reason: string
  confidence?: number
}

export type ParamFilter = {
  text: string             // matches key OR description, case-insensitive
  enabledOnly: boolean
  showLocked: boolean
}

export function applyFilter(cells: ParamCell[], filter: ParamFilter): ParamCell[] {
  const needle = filter.text.trim().toLowerCase()
  return cells.filter((c) => {
    if (filter.enabledOnly && !c.enabled) return false
    if (!filter.showLocked && c.locked) return false
    if (!needle) return true
    const hay = `${c.key} ${c.description ?? ''}`.toLowerCase()
    return hay.includes(needle)
  })
}

export function applySuggestion(cell: ParamCell, rec: Recommendation): ParamCell {
  if (cell.locked) return cell
  return { ...cell, enabled: true, value: rec.suggested_value as any }
}

export function applyAllSuggestions(cells: ParamCell[], recs: Recommendation[]): ParamCell[] {
  const map = new Map(recs.map((r) => [r.param_key, r]))
  return cells.map((c) => {
    const r = map.get(c.key)
    return r ? applySuggestion(c, r) : c
  })
}

export function resetToDefaults(cells: ParamCell[]): ParamCell[] {
  return cells.map((c) => (c.locked ? c : { ...c, enabled: false, value: c.default ?? null }))
}

export function disableAllOptional(cells: ParamCell[]): ParamCell[] {
  return cells.map((c) => (c.required || c.locked ? c : { ...c, enabled: false }))
}

export function diffBadge(cell: ParamCell): 'default' | 'modified' | 'locked' {
  if (cell.locked) return 'locked'
  if (cell.enabled && cell.value !== (cell.default ?? null)) return 'modified'
  return 'default'
}

export function toServeParams(cells: ParamCell[]): Record<string, unknown> {
  // Same opt-in semantics as the CLI: only enabled rows with non-null values are persisted.
  const out: Record<string, unknown> = {}
  for (const c of cells) {
    if (c.enabled && c.value != null && c.value !== '') out[c.key] = c.value
  }
  return out
}
```

- [ ] **Step 1: Write the failing tests** (one per exported function, covering edge cases — empty input, all-locked, mixed enabled+disabled, filter on description).

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Run — PASS** (`npm run test -- paramCell`).

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(dashboard): pure-functional ParamCell helpers (filter/suggestion/reset/diff)"
```

---

## Task 5: `useParamGridState` hook (local state machine)

**Files:**
- Create: `dashboard/src/features/params/useParamGridState.ts`
- Create: `dashboard/src/features/params/__tests__/useParamGridState.test.ts`

Wraps:
- Local mutable `cells: ParamCell[]` (initial = props, then mutated locally on edits)
- `filter: ParamFilter`
- Derived: `visibleCells` (after filter)
- Actions: `toggleEnabled(key)`, `setValue(key, v)`, `applySuggestion(key, rec)`, `applyAllSuggestions(recs)`, `resetToDefaults()`, `disableAllOptional()`, `setFilter(partial)`
- `isDirty` (any cell differs from initial)
- `serveParams()` → `Record<string, unknown>`

```ts
import { useMemo, useReducer } from 'react'
import {
  applyAllSuggestions, applyFilter, disableAllOptional, ParamCell,
  ParamFilter, Recommendation, resetToDefaults, toServeParams,
} from '@/lib/paramCell'

type Action =
  | { type: 'toggle'; key: string }
  | { type: 'set'; key: string; value: unknown }
  | { type: 'applyOne'; key: string; rec: Recommendation }
  | { type: 'applyAll'; recs: Recommendation[] }
  | { type: 'reset' }
  | { type: 'disableOptional' }
  | { type: 'replaceAll'; cells: ParamCell[] }
  | { type: 'filter'; partial: Partial<ParamFilter> }

interface State {
  initial: ParamCell[]
  cells: ParamCell[]
  filter: ParamFilter
}

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'toggle':
      return { ...s, cells: s.cells.map((c) => c.key === a.key && !c.locked ? { ...c, enabled: !c.enabled } : c) }
    case 'set':
      return { ...s, cells: s.cells.map((c) => c.key === a.key && !c.locked ? { ...c, value: a.value, enabled: true } : c) }
    case 'applyOne':
      return { ...s, cells: s.cells.map((c) => c.key === a.key && !c.locked ? { ...c, enabled: true, value: a.rec.suggested_value as any } : c) }
    case 'applyAll':
      return { ...s, cells: applyAllSuggestions(s.cells, a.recs) }
    case 'reset':
      return { ...s, cells: resetToDefaults(s.initial) }
    case 'disableOptional':
      return { ...s, cells: disableAllOptional(s.cells) }
    case 'replaceAll':
      return { initial: a.cells, cells: a.cells, filter: s.filter }
    case 'filter':
      return { ...s, filter: { ...s.filter, ...a.partial } }
  }
}

export function useParamGridState(initial: ParamCell[]) {
  const [state, dispatch] = useReducer(reducer, {
    initial,
    cells: initial,
    filter: { text: '', enabledOnly: false, showLocked: true },
  })

  const visibleCells = useMemo(() => applyFilter(state.cells, state.filter), [state.cells, state.filter])
  const isDirty = useMemo(() => JSON.stringify(state.cells) !== JSON.stringify(state.initial), [state.cells, state.initial])

  return {
    cells: state.cells,
    visibleCells,
    filter: state.filter,
    isDirty,
    toggleEnabled: (key: string) => dispatch({ type: 'toggle', key }),
    setValue: (key: string, value: unknown) => dispatch({ type: 'set', key, value }),
    applySuggestion: (key: string, rec: Recommendation) => dispatch({ type: 'applyOne', key, rec }),
    applyAllSuggestions: (recs: Recommendation[]) => dispatch({ type: 'applyAll', recs }),
    resetToDefaults: () => dispatch({ type: 'reset' }),
    disableAllOptional: () => dispatch({ type: 'disableOptional' }),
    replaceAll: (cells: ParamCell[]) => dispatch({ type: 'replaceAll', cells }),
    setFilter: (partial: Partial<ParamFilter>) => dispatch({ type: 'filter', partial }),
    serveParams: () => toServeParams(state.cells),
  }
}
```

- [ ] **Step 1: Tests** — exercise every action; assert `isDirty` flips appropriately; assert filter narrows visibleCells correctly; assert toggle on locked cell is a no-op.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): useParamGridState reducer hook (toggle/set/filter/suggestions/reset)"
```

---

## Task 6: `<ParamValueInput>` — type-aware value editor

**Files:**
- Create: `dashboard/src/features/params/ParamValueInput.tsx`

Dispatches on `cell.type` (the param schema's `type` field):
- `string` → shadcn `Input`
- `int` / `number` → `Input type="number"`
- `bool` → shadcn `Switch`
- `path` → `Input` + small "folder" icon button (in v1, the icon does nothing — no native folder picker — but the visual cue is correct)
- `enum` → shadcn `Select` over `cell.choices`
- Unknown / missing type → `Input` (string fallback)

Renders disabled when `cell.locked === true` or when `!cell.enabled` (and shows a subtle "Click to enable" placeholder).

- [ ] **Step 1: Tests** — render with each type → assert correct shadcn primitive in the DOM.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): ParamValueInput dispatches on param type (string/int/bool/path/enum)"
```

---

## Task 7: `<ParamRow>` — single row UI

**Files:**
- Create: `dashboard/src/features/params/ParamRow.tsx`

Props: `cell: ParamCell`, `recommendation?: Recommendation`, plus callback handlers (`onToggle`, `onSetValue`, `onApplySuggestion`).

Layout (shadcn `TableRow`):
- Cell 1: `<Checkbox>` reflecting `cell.enabled`. Disabled if `cell.locked || cell.required`.
- Cell 2: `<code>` with `cell.key` + a small `Badge` showing `diffBadge(cell)` (`default` zinc, `modified` blue, `locked` amber).
- Cell 3: `<ParamValueInput cell={cell} onChange={...} />`.
- Cell 4: suggestion column — if `recommendation`, show suggested value + "Apply" button → calls `onApplySuggestion`. Else empty.
- Cell 5: lock icon if `cell.locked`, with tooltip explaining why.
- Cell 6: description on hover (shadcn `Tooltip` on the `?` icon).

- [ ] **Step 1: Tests** — render with various cell states; click toggle; click apply; assert correct callbacks.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): ParamRow with enabled/key/value/suggestion/lock/description columns"
```

---

## Task 8: `<ParamGrid>` — the flagship component

**Files:**
- Create: `dashboard/src/features/params/ParamGrid.tsx`
- Create: `dashboard/src/features/params/__tests__/ParamGrid.test.tsx`

Props:
```ts
interface ParamGridProps {
  cells: ParamCell[]                 // initial cells (from API)
  recommendations: Recommendation[]  // from /api/recommendations
  onSave?: (serveParams: Record<string, unknown>) => Promise<void>  // omit in read-only mode
  mode?: 'edit' | 'review'           // review = read-only, no toolbar
}
```

Layout:
- **Sticky toolbar** at the top:
  - `<Input placeholder="Filter…" />` (Ctrl+F shortcut binds focus)
  - `<Switch>` "Enabled only"
  - `<Switch>` "Show locked" (default on)
  - Bulk action menu: "Apply all suggestions", "Reset to defaults", "Disable all optional"
  - On the right: `isDirty` badge + Save button (calls `onSave(serveParams())`)
- `<Table>` with header `[ ] | key | value | suggestion | locked | desc`
- Body: `visibleCells.map(c => <ParamRow ... />)`
- Empty-filter state: "No params match the current filter."

Tests:
- Renders all cells initially.
- Typing in filter narrows the list.
- Toggling a row's checkbox marks dirty and updates the save button.
- Clicking "Apply all suggestions" applies all matching recs.
- "Reset to defaults" restores initial.
- Save button calls `onSave` with the correct `serveParams` shape.
- Locked cell's value input is disabled.

- [ ] **Step 1: Tests.**

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): ParamGrid (the flagship form) — filter, suggestions, bulk actions, dirty tracking"
```

---

## Task 9: Wire `<ParamGrid>` into `ConfigDetailPage`'s Params tab

**Files:**
- Modify: `dashboard/src/features/configs/ConfigDetailPage.tsx`
- Modify: `dashboard/src/features/configs/ParamsView.tsx` (now wraps `<ParamGrid>` in edit mode with save→PUT)

`ParamsView`:
- `useQuery(['configs', id, 'params'])`
- `useQuery(['recommendations', runtimeId, modelId])` — keys depend on the config's runtime+model
- `useMutation` against `PUT /api/configs/{id}` that sends `{...currentConfig, serve: {params: <new serveParams>}}`
- Renders `<ParamGrid cells={...} recommendations={...} onSave={...} />`
- On save success: toast + invalidate `['configs', id]` and `['configs', id, 'params']`
- On save error (e.g., `CONFIG_INVALID` with `errors: [...]`): pass into the grid's error display

- [ ] **Step 1: Test** — render `ParamsView` with mocked endpoints → toggle a row → click Save → assert PUT called with correct body → assert success toast.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): Config detail Params tab uses ParamGrid (replaces JSON dump)"
```

---

## Task 10: New-config wizard — step shell + state

**Files:**
- Create: `dashboard/src/features/configs/wizard/NewConfigWizard.tsx`
- Create: `dashboard/src/features/configs/wizard/wizardState.ts` (Zustand store local to the wizard, or a `useReducer` — pick one and stick to it)

The wizard is a 5-step linear flow:
1. Pick runtime
2. Pick model (optional — runtime may not require one)
3. Edit params (uses `<ParamGrid>` with default-params + recommendations)
4. Review (read-only `<ParamGrid mode="review">` + computed config YAML preview + id input)
5. Save (POST + redirect to detail)

`NewConfigWizard`:
- Renders a step indicator + current step's component
- Handles "Back" / "Next" navigation, with each step's "Next" gated on validation
- Owns shared state: `{runtimeId, modelId, params: ParamCell[], configId}`

State stored in a `useReducer` co-located with the wizard:

```ts
interface WizardState {
  step: 1 | 2 | 3 | 4 | 5
  runtimeId: string | null
  modelId: string | null
  params: ParamCell[] | null
  configId: string  // proposed id, default = `${runtime}__${model}__default`
}
```

- [ ] **Step 1: Skeleton test** — render wizard, assert step 1 visible, click Next when no runtime selected → still on step 1 + validation message.

- [ ] **Step 2: Implement the shell + state reducer.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(dashboard): new-config wizard shell (5-step state machine)"
```

---

## Task 11: Wizard step 1 — Pick runtime

**Files:**
- Create: `dashboard/src/features/configs/wizard/StepPickRuntime.tsx`

Uses `useQuery(['runtimes'])` → `<Select>` over installed runtimes (uninstalled runtimes shown but disabled with "Install first"). Default selection: most recently used (read from `state/history.jsonl` if cheap; else first installed). On selection: dispatch + advance to step 2.

- [ ] **Step 1: Test** — renders runtimes, selecting one calls dispatch.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): wizard step 1 — pick runtime"
```

---

## Task 12: Wizard step 2 — Pick model (optional)

**Files:**
- Create: `dashboard/src/features/configs/wizard/StepPickModel.tsx`

Uses `useQuery(['models'])` filtered by formats the runtime supports (e.g., llamacpp → gguf only). Includes a "Skip — no model" option for runtimes where model is optional (stub-runtime).

- [ ] **Step 1: Test + implement + commit** — same pattern.

```bash
git commit -m "feat(dashboard): wizard step 2 — pick model (optional, filtered by runtime format)"
```

---

## Task 13: Wizard step 3 — Params (with advisor)

**Files:**
- Create: `dashboard/src/features/configs/wizard/StepParams.tsx`

- Fetches `useQuery(['runtimes', runtimeId, 'default-params', modelId])`.
- Fetches `useQuery(['recommendations', runtimeId, modelId])`.
- Renders `<ParamGrid cells={...} recommendations={...} mode="edit" />` with no `onSave` — instead, on Next click, dispatch `{type: 'setParams', params: gridRef.current.cells}` and advance.
- A small advisor card above the grid summarizes the highest-confidence recommendations with an "Apply all" button.

- [ ] **Step 1: Test** — renders param grid with cells, advisor card shows recs, "Apply all" propagates into grid.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): wizard step 3 — params via ParamGrid with advisor"
```

---

## Task 14: Wizard step 4 — Review

**Files:**
- Create: `dashboard/src/features/configs/wizard/StepReview.tsx`

- Renders a `<ParamGrid mode="review">` over the in-progress params (read-only).
- Shows the computed config YAML preview (a `<pre>` rendering of the about-to-be-saved YAML, using the same client-side serializer the `paramCell.ts` helpers produce).
- Lets the user override the config id (default-built from runtime + model + "default", validated for uniqueness with a `useQuery(['configs'])`).
- "Back" lets them return to step 3. "Save" advances to step 5.

- [ ] **Step 1: Test** — id collision shows error; otherwise Next advances.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): wizard step 4 — review with id uniqueness check"
```

---

## Task 15: Wizard step 5 — Save

**Files:**
- Create: `dashboard/src/features/configs/wizard/StepSave.tsx`

- `useMutation` against `POST /api/configs` with the full config dict.
- Shows a spinner; on success: toast + redirect to `/configs/${configId}`. On error: show inline + "Go back" button.

- [ ] **Step 1: Test** — happy save → redirect; CONFIG_INVALID error → display.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): wizard step 5 — save + redirect on success"
```

---

## Task 16: Replace `NewConfigPage` body with wizard

**Files:**
- Modify: `dashboard/src/features/configs/NewConfigPage.tsx`

```tsx
import { NewConfigWizard } from './wizard/NewConfigWizard'

export function NewConfigPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Create a new config</h1>
      <NewConfigWizard />
    </div>
  )
}
```

Plan 2's `<ConfigForm>` (raw editor) remains available from the ConfigDetailPage's Raw YAML tab as a power-user fallback.

- [ ] **Step 1: Test** — visiting `/configs/new` shows the wizard's step 1.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): NewConfigPage delegates to the 5-step wizard"
```

---

## Task 17: End-to-end smoke + PR

- [ ] **Step 1: Local smoke**
  - Click "New config" on Configs page → wizard appears.
  - Pick runtime, pick model, edit params (toggle some, apply a suggestion), review, save.
  - Confirm new config appears in the Configs list with correct contents.
  - Open the new config's detail → Params tab → see the grid, edit a value, save, confirm persistence.

- [ ] **Step 2: Tests green**

```bash
uv run pytest -q
cd dashboard && npm run typecheck && npm run test && npm run build
scripts/regen-api-client.sh --check
```

- [ ] **Step 3: PR**

```bash
git push -u origin feat/web-dashboard-param-grid
gh pr create --title "feat(dashboard): param grid + new-config wizard (Plan 3/5)" --body "..."
```

---

## Self-review

1. **Spec coverage:** §8.7 ParamGrid (table + filter + suggestion column + bulk actions + diff badges + opt-in semantics on save) is implemented; §8.9 Configs wizard (5-step pick-runtime → pick-model → params → review → save) is implemented.
2. **Placeholder scan:** none.
3. **Type consistency:** `ParamCell` is the exact type emitted by OpenAPI → consumed unchanged. `Recommendation` shape matches `/api/recommendations` response. Wizard's `WizardState` is internal and used only inside the wizard folder.
4. **DRY:** `ParamGrid` is one component used both in config-detail editing and wizard step 3+4 (with `mode` prop). `paramCell.ts` helpers are pure and reused across grid, state hook, and wizard preview.
5. **Branch hygiene:** `feat/web-dashboard-param-grid` from `main` after Plan 2 merges.
6. **Conventional commits:** all `feat(dashboard):` / `feat(webapi):` / `chore(...)`.
