# Serve / Build Param Opt-In Design

**Date:** 2026-05-19  
**Status:** Approved (approach 1)  
**Supersedes in spirit:** implicit “default fill + ship all” behavior documented in `add-a-runtime.md` and implemented in `validate_params` / `cells_from_specs`.

## Problem

Today, `loco config setup` and runtime install pre-fill every param that has a schema `default`, save the full map to YAML / `.installed`, and `validate_params` back-fills missing keys with defaults. At serve time, those values become env vars and CLI flags. Users cannot express “let the runtime decide” for optional knobs — defaults are shipped as real overrides.

Catalog `default` values were meant as suggestions, not as implicit configuration.

## Goals

1. **Opt-in shipping** — optional params are omitted from YAML / env unless explicitly enabled and given a value.
2. **Unified semantics** — config **serve** params and runtime **build** params use the same grid + enable model.
3. **Clear UI** — list view shows enabled vs disabled vs enabled-but-empty; advisor suggestions visible separately from values.
4. **No catalog defaults** — remove `default:` from `params.yaml`; suggestions come from `recommend()` / advisor only (v1: often blank).
5. **Strict adaptation** — no auto-migration of old configs; users re-run setup or edit YAML.

## Non-goals (v1)

- Auto-migration command or doctor-driven cleanup of legacy full-param configs.
- Advisor-driven bulk enable (future: advisor proposes values separately).
- Changing YAML top-level shape (`serve.params` remains a flat map).
- `loco config edit` interactive wizard (still out of scope).

---

## Core semantics

### Shipping rule

| Param kind | Grid default | Space toggle | In saved map | Shipped to env |
|------------|--------------|--------------|--------------|----------------|
| Optional | `enabled=false`, `value=""` | Yes | Only if enabled + valid value | Only if key in map |
| `required: true` | `enabled=true`, locked | No | Always (must have value) | Yes |
| `bind: model_path` | `enabled=true`, locked, hidden in list | No | Always (auto-filled) | Yes |

**Presence in YAML = enabled.** Disabled optional params are **absent** from `serve.params` / `build_params`.

**Save validation:** enabled optional row with empty value → hard error (user must open detail and set a value, or disable the row).

**Serve / build runtime:** unchanged at the shell layer — `append_arg_if_set` and friends already skip unset env vars. The CLI must stop injecting defaults upstream.

### Catalog (`params.yaml`)

- **Remove `default:`** from all official catalogs (`llamacpp`, `vllm`, `stub-runtime`, custom template).
- Keep: `type`, `required`, `env`, `tier`, `bind`, `description`, `prompt`, `values` (enum).
- **`validate_params`:** validate and coerce **only keys present** in the input map; enforce `required`; **do not** back-fill `default` (field removed from schema).
- **`parse_schema`:** ignore or reject `default` if present during transition (prefer **reject with clear error** so stale catalogs are caught in CI/tests).

### Suggestions (UI only)

- **Source:** `recommend(runtime_id, key, …)` when implemented; otherwise empty.
- **Display:** right column in param list (truncated); full text in detail view prefixed `Suggestion:`.
- Catalog does **not** supply fallback suggestion text in v1.

### Legacy configs

- No migration tooling.
- Existing YAML with many keys remains **structurally valid** (keys present → still shipped) until the user re-runs `loco config setup` or deletes keys manually.
- Document that pre-opt-in “full default” configs should be recreated for intended behavior.

---

## Approach: enable flag on grid rows (approach 1)

Single param grid for **config setup** and **runtime install/rebuild**. Each `ParamCell` gains `enabled: bool`.

### `ParamCell` changes

```python
@dataclass
class ParamCell:
    ...
    enabled: bool = False
```

Initialization in `cells_from_specs`:

- Optional spec → `enabled=False`, `value=""`.
- `required` or `bind` (non-readonly skip list) → `enabled=True`; bound `model_path` → token value as today.
- `default` field no longer read from catalog.

### List view (params step)

| Column | Content |
|--------|---------|
| Indicator | `[ ]` / `[x]` when toggleable; `[•]` when locked on |
| Key | param name |
| Value | blank if disabled; user value if enabled |
| Suggestion | advisor hint (dim), optional |

**Keybindings (TTY):**

| Key | Action |
|-----|--------|
| **Space** | Toggle `enabled` on optional rows (replaces bool toggle in list view) |
| **Enter** | Open detail to edit **value** (all types including bool) |
| **Ctrl+A** | Toggle advanced tier visibility (unchanged) |

**Remove:** Space-to-toggle-bool in list navigation (`param_grid.py::_toggle_bool_at`).

**Row styling (`cell_state` extension):**

- `disabled` — optional, `enabled=false`
- `enabled-empty` — enabled but value blank (warn styling; blocks save)
- `enabled-set` — enabled with value
- `locked` — required / bound (always enabled)

Plain fallback (`param_grid_plain.py`): same semantics via row markers and prompts.

### Save path

On save (`ParamGridResult`):

1. Collect cells where `enabled` **or** locked required/bound.
2. Drop disabled optional keys entirely.
3. Validate each included key has non-empty coercible value (except bool `false` is valid).
4. Pass filtered map to `validate_params` → write YAML / `.installed`.

`walk_tier` advanced-key omission on save is **subsumed** by enable flags; install/rebuild uses `edit_params` grid instead of sequential `walk_tier` fill.

### Build install flow

Replace `_resolve_build_params` interactive path:

- Present full build schema in the same param grid (meta step omitted or minimal).
- User enables optional build params and sets values in detail.
- CLI `--param k=v` pre-enables those keys (and sets value) before grid opens.
- `--yes` non-interactive: only flags + required keys; no grid default fill.

`.installed` `build_params` stores the filtered map only.

### Serve flow

`config_cmd.do_config_setup` / `do_config_new`:

- Save filtered `serve.params`.
- `loco serve` → `_serve_env_from_params` unchanged: only keys in map get env vars.

### Doctor / validate

- `loco config validate`: required keys must appear in map; unknown keys error; no default fill.
- Optional: future warning if map size exceeds N (not v1).

---

## Files to change (implementation reference)

| Area | Files |
|------|--------|
| Models | `param_grid_models.py`, `param_grid_build.py` |
| TUI | `param_grid.py`, `param_grid_layout.py`, `param_grid_theme.py`, `param_grid_plain.py` |
| Validation | `params.py` (`parse_schema`, `validate_params`) |
| Commands | `config_cmd.py`, `runtime_cmd.py` |
| Wizards | `wizards.py` (deprecate or narrow `walk_tier`) |
| Catalogs | `runtimes/llamacpp/params.yaml`, `runtimes/vllm/params.yaml`, `runtimes/stub-runtime/params.yaml`, custom template in `runtime_cmd.py` |
| Tests | `test_params.py`, `test_param_grid*.py`, config/runtime integration tests |
| Docs | `add-a-runtime.md`, `wizards.md`, `add-a-config.md` |

---

## Testing strategy

1. **Unit:** `validate_params` no longer fills defaults; required missing errors; empty enabled row rejected at save.
2. **Unit:** `cells_from_specs` optional starts disabled; required locked on.
3. **Unit:** grid Space toggles enable only; bool change requires detail.
4. **Integration:** config setup saves only enabled keys; serve env omits disabled.
5. **Integration:** runtime install with grid saves sparse `build_params`.
6. **Regression:** bound `model_path` still auto-filled and hidden.

---

## Versioning

**Breaking change** (`feat!:`): param shipping semantics + catalog schema (`default` removed). Users on old full-param configs should re-run setup. Release note: opt-in params; recreate configs.

---

## Open questions (deferred)

- Advisor “apply suggestion” bulk action in grid.
- Validate warning for legacy bloated configs.
- Whether to reject unknown `default` key in `parse_schema` vs warn once.

**Decision for v1:** reject `default` in `parse_schema` with actionable error pointing to advisor.
