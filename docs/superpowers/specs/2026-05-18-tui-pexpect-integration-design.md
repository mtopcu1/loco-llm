# TUI Pexpect Integration Test Design

**Date:** 2026-05-18  
**Status:** Approved  
**Scope:** Phase 1 — `llm config setup` + `llm runtime setup` (Option B). Phase 2 starter: `runtime install` walk_tier (implemented).

## Problem

Integration tests today use `typer.testing.CliRunner` and **mock** wizard entry points (`edit_params`, `select`, `walk_tier`, etc.). They validate CLI wiring, filesystem side effects, and exit codes, but **never exercise the prompt_toolkit param grid or questionary menus** on a real PTY.

Unit tests cover param grid state machines with mocked `Application`. The gap is **scripted end-to-end TUI journeys** that send keys and assert on screen text plus post-run artifacts.

## Goals

1. Add **code-driven pexpect tests** that drive real subprocesses with a PTY.
2. Cover **Phase 1 workflows:** `llm config setup` and `llm runtime setup`.
3. Use **stub-runtime** and **fake registry models** (no GPU, no large downloads).
4. Map **every command/workflow** to expected behavior and existing vs new test coverage.
5. Cover **edge cases** for param grid navigation, validation, abort, and save semantics.

## Non-goals

- Replacing existing `CliRunner` integration tests (they stay as fast contract tests).
- Pexpect for every command (lifecycle, serve, model pull, doctor remain mock/non-TUI).
- Windows-native PTY runs (skip on Windows; run in WSL/Linux CI).
- Golden full-screen transcript snapshots (too brittle).

---

## Test taxonomy

| Tier | Mechanism | What it proves |
|------|-----------|----------------|
| **Unit** | pytest + mocks | Param grid state, wizards helpers, validation |
| **Integration (mock)** | `CliRunner` + `monkeypatch` wizards | Command wiring, YAML/registry/files, exit codes |
| **Integration (TUI)** | **pexpect** + temp repo fixture | Real PTY menus, param grid keys, questionary selects |

Existing integration tests are **not** pexpect — they bypass TUI. New TUI tier **complements** them.

---

## Harness design

### Layout

```
tests/
  tui/
    conftest.py           # markers, skipif, seed_repo(), spawn_llm()
    keys.py               # ESC, CTRL_S, CTRL_C, ARROW_* helpers
    fixtures/
      seed.py             # copy runtimes, write settings, fake model registry
    workflows/
      config_setup.py     # reusable key sequences for config wizard
      runtime_setup.py    # preset + custom runtime setup flows
  integration/
    test_tui_config_setup.py
    test_tui_runtime_setup.py
```

### `spawn_llm(args, *, env, cwd)`

- Command: `{sys.executable} -m llm_cli.main` with args (or installed `llm` if `LLM_TEST_USE_ENTRYPOINT=1`).
- Env: `PYTHONPATH=src`, isolated `HOME`, `XDG_CONFIG_HOME`, `TERM=xterm-256color`, `COLUMNS=100`, `LINES=30`.
- **Do not** set `LLM_FORCE_PLAIN` — TUI must run (`stdout.isatty()` true via PTY).
- Timeouts per `expect` step (default 5s); fail with decoded buffer on timeout.

### `seed_repo(tmp_path) -> RepoFixture`

Same semantics as existing `_seed_repo` in integration tests, but **filesystem-only** (no monkeypatch — child process reads real paths):

1. Copy workspace `runtimes/` → `{tmp}/runtimes/`.
2. `mkdir {tmp}/configs`.
3. Write `save_settings({"data_root": ..., "repo_root": ...})` under temp `HOME`.
4. Optionally write fake model registry JSON under `{data_root}/models/registry.json` (or use `upsert_entry` in fixture setup before spawn).
5. Expose paths: `repo_root`, `configs_dir`, `models_dir`, `settings_path`.

### Fake model fixture (`qwen-7b`)

Registry entry matching existing integration tests:

- `format: gguf`, `primary: m.gguf`, `total_size_bytes: 8 GiB`
- Used for `llamacpp` config setup flows requiring `--model` / model picker.

### Markers

```python
pytestmark = pytest.mark.tui

@pytest.mark.skipif(sys.platform == "win32", reason="pexpect PTY tests require Unix")
```

Run: `pytest -m tui` on Linux/WSL. Default full suite skips TUI on Windows.

### Dependencies

Add to `[project.optional-dependencies] dev`:

```toml
"pexpect>=4.9; sys_platform != 'win32'",
```

Register marker in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["tui: PTY-driven TUI integration tests (Unix only)"]
```

### Assertion style

- **During run:** substring `expect` on decoded output (`Configuration`, `Parameters`, `Save`, `aborted`, error messages). Strip ANSI optionally via helper.
- **After run:** exit status, file existence, YAML field presence (reuse parsing helpers from mock integration tests).
- **Avoid:** exact layout/position assertions.

---

## Command & workflow inventory

Legend: **Mock** = existing `CliRunner`+patch; **TUI** = new pexpect; **N/A** = non-interactive / no wizard.

### Top-level

| Command | Interactive UI | Expected behavior | Existing tests | TUI phase |
|---------|----------------|-------------------|----------------|-----------|
| `llm setup --default` | No (flags only) | Writes settings, prints next steps, **no** chain | `test_cli_setup.py` | N/A |
| `llm setup` (interactive) | typer.prompt + **chain** | Settings → optional runtime/model/config/serve chain | `test_cli_setup_chain.py` (chain mocked) | Phase 3 (partial) |
| `llm list` | No | Tables of runtimes/models/configs | `test_cli_milestone2.py` | N/A |
| `llm specs` | No | Regenerates specs.md block | `test_cli_specs.py` | N/A |
| `llm advisor` | `select` if no flags | VRAM recommendations; optional config offer | `test_cli_advisor.py` | Phase 3 (select only) |
| `llm serve` / `switch` / `stop` / `status` / `logs` | No | Lifecycle dispatch | `test_cli_serve.py`, `test_cli_lifecycle.py` | N/A |
| `llm doctor` | No | Prereq checks | `test_cli_doctor.py` | N/A |

### `llm settings`

| Subcommand | UI | Expected behavior | Existing tests | TUI |
|------------|-----|-------------------|----------------|-----|
| `show`, `set`, `path` | No | Read/write `~/.config/llm/config.yaml` | `test_cli_settings.py` | N/A |

### `llm runtime`

| Subcommand | UI | Expected behavior | Existing tests | TUI |
|------------|-----|-------------------|----------------|-----|
| `list`, `info`, `uninstall` | No | Discovery / records | `test_cli_runtime.py` | N/A |
| **`setup`** | **`select` + preset/custom wizards** | Preset → install official runtime; Custom → write manifest/params/serve | `test_cli_runtime_setup.py` (mocked) | **Phase 1** |
| `install` | **`walk_tier`** if build params missing | Runs build/verify; writes `.installed` | `test_cli_runtime.py` (walk_tier mocked) | Phase 2 |
| `rebuild` | Same as install with `--reset` | Re-prompt or `--yes` defaults | `test_cli_runtime.py` | Phase 2 |
| `install`/`rebuild` custom kind | No | Error → use `runtime setup` | `test_cli_runtime_setup.py` | N/A |

### `llm model`

| Subcommand | UI | Expected behavior | Existing tests | TUI |
|------------|-----|-------------------|----------------|-----|
| `list`, `info`, `remove` | No | Registry CRUD | `test_cli_model.py` | N/A |
| `pull` | Duplicate menu in **setup chain only** | HF download, registry upsert | `test_cli_model.py` (HTTP mocked) | N/A (network) |
| Chain duplicate menu | `select` 4-way | keep / force / rename / skip | None dedicated | Phase 3 |

### `llm config`

| Subcommand | UI | Expected behavior | Existing tests | TUI |
|------------|-----|-------------------|----------------|-----|
| `new` | No | Non-interactive YAML from `--param` | `test_cli_config_new.py` | N/A |
| **`setup`** | **`select`** (optional) + **`edit_params` param grid** | Meta → params → save YAML | `test_cli_config_setup.py` (edit_params mocked) | **Phase 1** |
| `show`, `validate` | No | Load/validate configs | milestone tests | N/A |

### Setup chain (`run_setup_chain`)

| Step | UI | Expected behavior | Existing tests | TUI |
|------|-----|-------------------|----------------|-----|
| Runtime? | `confirm` | Calls `interactive_runtime_setup` | chain mocked | Phase 3 |
| HF URL | `text` | Pull or skip | chain mocked | N/A |
| Config? | `confirm` | Calls `do_config_setup` | chain mocked | Phase 3 |
| Serve? | `confirm` | Background serve | chain mocked | N/A |

---

## Phase 1 — TUI scenarios

### A. `llm config setup`

**Fixtures:** seeded repo + fake `qwen-7b` + full workspace runtimes.

#### A1 — Happy path (llamacpp + model, flags pre-filled)

```
llm config setup --runtime llamacpp --model qwen-7b
```

| Step | Keys / action | Expect | Post-condition |
|------|---------------|--------|----------------|
| Land on meta | — | `Configuration` or `host` | |
| Advance | `→` or footer Next | `Parameters` | |
| Save | `Ctrl+S` or footer Save | process exits 0 | `configs/llamacpp__qwen-7b__default.yaml` exists |
| YAML | — | — | `gguf_path: ${model_path}`, `host`, `port` |

#### A2 — Full interactive pickers

```
llm config setup
```

| Step | Keys | Expect |
|------|------|--------|
| Runtime select | ↓ + Enter on `llamacpp` | model picker or params |
| Model select | pick `qwen-7b` | meta or params |

#### A3 — Abort paths

| Case | Keys | Expect | Post |
|------|------|--------|------|
| Meta abort | `Ctrl+C` / `Esc` | `aborted` | no YAML |
| Params abort | navigate to params → `Ctrl+C` | `aborted` | no YAML |

#### A4 — Navigation

| Case | Keys | Expect |
|------|------|--------|
| Params → meta back | `Esc` or footer Back from params | `Configuration` |
| Page nav only | `→` from params last page | stays on params (no save) |
| Footer focus | `↓` on last meta row | footer visible (`Back`/`Next`) |

#### A5 — Detail edit

| Case | Keys | Expect | Post |
|------|------|--------|------|
| Change port | Enter on `port` → type `9090` → Enter → save | | `port: 9090` in YAML |
| Invalid port | Enter → `abc` → Enter | validation error visible | no save until fixed |
| Bool toggle | Space on `flash_attn` (or other bool) | value toggles in list | reflected in YAML |

#### A6 — Advanced tier

| Case | Keys | Expect | Post |
|------|------|--------|------|
| Reveal advanced | `Ctrl+A` | advanced param row appears | |
| Save without advanced | save without Ctrl+A | advanced keys omitted from YAML params | |
| Save with advanced | Ctrl+A → save | advanced key present | |

#### A7 — Readonly / bound path

| Case | Expect | Post |
|------|--------|------|
| `gguf_path` hidden in list | not in visible param rows | |
| Saved binding | — | `gguf_path: ${model_path}` in YAML |

#### A8 — stub-runtime (no model)

```
llm config setup --runtime stub-runtime
```

| Step | Expect | Post |
|------|--------|------|
| No model picker | skips model `select` | |
| Meta + empty/small params | save succeeds | `configs/stub-runtime__default.yaml` (or preset id) |

#### A9 — Error paths (non-TUI exit before grid)

| Case | Setup | Expect |
|------|-------|--------|
| No compatible models | empty registry | `no compatible models`, exit ≠ 0 |
| Model on no-model runtime | `--runtime stub-runtime --model qwen-7b` | error before grid |

*Maps mock tests:* `test_config_setup_writes_valid_yaml`, `test_config_setup_skips_bound_path_when_model_set`, `test_config_setup_abort_writes_nothing`, `test_config_setup_no_compatible_models`.

---

### B. `llm runtime setup`

**Fixtures:** seeded repo with workspace `runtimes/` (includes `stub-runtime`, `llamacpp`).

#### B1 — Preset → stub-runtime install

```
llm runtime setup
```

| Step | Keys | Expect | Post |
|------|------|--------|------|
| Branch | pick `Preset — install an official runtime` | preset list | |
| Preset | pick `stub-runtime` | build output / success | `.installed` under data runtimes dir |
| stdout | — | `stub-runtime` echoed | |

*Note:* `stub-runtime` has `build: {}` — install runs build.sh without param grid.

*Maps mock test:* `test_runtime_setup_preset_lists_official_runtimes`.

#### B2 — Preset abort

| Step | Keys | Expect |
|------|------|--------|
| Ctrl+C on branch select | `Ctrl+C` | clean exit / no install |

#### B3 — Custom runtime (template path)

Minimal scripted flow (short answers):

| Step | Input | Expect | Post |
|------|-------|--------|------|
| Branch | Custom | slug prompt | |
| id | `tui-custom` | display name prompt | |
| formats | checkbox: `none` or gguf | serve mode select | |
| template | default invocation | files written | `runtimes/tui-custom/manifest.yaml` |
| | | | `kind: custom`, `.installed` |

*Maps mock tests:* `test_runtime_setup_custom_writes_all_files`, `test_runtime_setup_custom_refuses_existing_id` (existing id → error message, no files).

#### B4 — Custom refuses duplicate id

Pre-create `runtimes/llamacpp`. Run custom setup with id `llamacpp` → expect `already exists`, exit ≠ 0.

---

## Phase 2 — follow-up TUI (not Phase 1)

| Workflow | Why deferred |
|----------|--------------|
| `runtime install <id>` with **walk_tier** | Needs tiered build fixture runtime in temp repo; stub-runtime has empty `build` |
| `runtime install` abort mid-grid | Same harness as config grid |
| `llm setup` chain first `confirm` + runtime setup | Longer script; compose Phase 1 workflows |
| `llm advisor` interactive `select` | Simple questionary; lower risk than param grid |

Phase 2 reuses `workflows/` helpers and `walk_tier` param grid scenarios (advanced toggle, abort).

---

## Phase 3 — optional

- Setup chain end-to-end with stub-runtime + skip model URL + config setup TUI segment.
- Duplicate model registration menu during chain (4-way select).
- Custom runtime **Editor** mode — skip in TUI (requires `$EDITOR` subprocess); covered by mock tests only.

---

## Error handling & stability

| Concern | Mitigation |
|---------|------------|
| Flaky `expect` | Fixed `COLUMNS`/`LINES`; substring not regex anchors; strip ANSI |
| Zombie processes | `child.close(force=True)` in fixture teardown |
| Slow CI | Phase 1 target ≤ 15 tests, ~2–3 min total on WSL |
| Missing pexpect on Windows dev | `skipif win32`; dev docs note `pytest -m tui` in WSL |
| questionary vs plain | PTY always has TTY → questionary path for `select`/`confirm`; param grid uses prompt_toolkit |

---

## CI recommendation

```yaml
# Example job snippet (WSL or ubuntu-latest)
- run: pip install -e ".[dev]"
- run: pytest -m tui -v
```

Default PR job runs `pytest` without `-m tui` on Windows if needed; Linux job runs TUI suite.

---

## Success criteria

1. Phase 1 pexpect suite passes on Linux/WSL with **≥ 12 scenarios** covering A1–A9 and B1–B4 core cases.
2. No existing integration tests removed or weakened.
3. Documented mapping (this spec) from mock tests → TUI equivalents.
4. Failures print last PTY buffer for debugging.

---

## Self-review checklist

- [x] No TBD placeholders — phases explicit.
- [x] Phase 1 scope matches user Option B (config + runtime setup).
- [x] Full command inventory with test mapping included.
- [x] Consistent with param grid design (`2026-05-18-param-grid-list-detail-design.md`).
- [x] Windows skip and WSL CI documented.
- [x] Model/registry fixtures align with `test_cli_config_new.py` / `test_cli_config_setup.py`.

---

## Implementation status (2026-05-18)

Shipped in commits `aa566b2`, `2ea5e14`, `6e89666`:

- Harness: `tests/tui/` (`seed.py`, `session.py`, `keys.py`, `workflows.py`)
- PTY tests: `test_tui_config_setup.py`, `test_tui_runtime_setup.py`, `test_tui_runtime_install.py`
- WSL result: 15 passed, 1 skipped (`test_tui_runtime_setup_abort_on_branch` — questionary cancel in pexpect PTY)
- Product fix: questionary cancel → `KeyboardInterrupt`; `walk_tier.aborted` propagates through `runtime install`

Known gaps vs full scenario catalog: A2 interactive pickers, A5 bool toggle, A6 advanced tier, B2 PTY abort (CliRunner covered). Phase 3 not started.
