# `llm setup` UX audit (interactive walkthrough)

**Branch:** `feat/ux-improvements`  
**Date:** 2026-05-20  
**Environment:** Windows 11, PowerShell, Cursor + **smart-terminal-mcp** (PTY)  
**CLI version:** `llm 1.3.0` (editable install from repo root after worktree cleanup)

Walkthrough used isolated settings via `XDG_CONFIG_HOME` under `.ux-walkthrough/` so the host `~/.config/llm/config.yaml` was not modified.

---

## Executive summary

| Area | Verdict |
|------|---------|
| **Typer prompts** (data_root, confirms, dir overrides) | Work well over PTY; defaults and `[Y/n]` are readable |
| **Questionary menus** (runtime/model/config chain) | Usable but **arrow-key navigation is unreliable** via agent PTY; garbled UI and wrong selection observed |
| **Post-settings chain** | Skipping steps (`n`, empty URL) behaves as expected |
| **`llm setup --default`** | Clean; skips chain; prints next steps |
| **Windows runtime install (stub-runtime)** | **Fails**: `LLM_DATA_ROOT` not visible inside WSL bash for `build.sh` |
| **Dev install hygiene** | **Critical**: stale editable target after deleting git worktrees breaks `llm` entirely |

---

## Methodology

1. Git cleanup (worktrees + merged branches) and branch `feat/ux-improvements`.
2. `terminal_start` with `XDG_CONFIG_HOME` + `LLM_DEFAULT_DATA_ROOT` pointing at `.ux-walkthrough/`.
3. Drive `llm setup` with `terminal_write` / `terminal_read` / `terminal_send_key`.
4. Spot-check `llm runtime setup`, `llm setup --default`, granular directory overrides.

### smart-terminal MCP notes (tooling, not `llm` bugs)

- `terminal_exec` often returns **empty `output`**; call **`terminal_read`** afterward to get PTY buffer content.
- `terminal_run` is better for one-shot commands (returns stdout directly).
- MCP server process may not inherit the same PATH as an interactive Cursor terminal (`uv` was `ENOENT` via `terminal_run`); `llm` on PATH worked after reinstalling editable package from main.

---

## Flow map

```text
llm setup
├── [Typer] data_root prompt (default from LLM_DEFAULT_DATA_ROOT or ~/llm)
├── [Typer] "Use default subdirectory layout?" [Y/n]
│   └── if No → optional overrides for runtimes_dir, models_dir, cache_dir (empty = derive)
├── [Typer] "Use this checkout as repo_root?" [Y/n]  (only in git checkout)
├── write config.yaml + ensure_data_dirs + summary lines
└── run_setup_chain()  (skipped entirely with --default)
    ├── [Questionary] Install / register runtime? [Y/n]
    ├── [wiz.text] Hugging Face URL (empty = skip)
    ├── [Questionary] Create launch config? [Y/n]
    │   └── config wizard (runtime select, model, params, …)
    ├── [Questionary] Serve in background? [Y/n]
    └── [Questionary] Install web dashboard? [Y/n]
```

---

## Phase 1 — Settings (Typer)

### Observed behavior

| Step | Input | Result |
|------|-------|--------|
| `data_root` | Enter (default) | Used `.ux-walkthrough/data` from `LLM_DEFAULT_DATA_ROOT` |
| Default layout | Enter (Y) | Derived `runtimes/`, `models/`, `cache/` under data_root |
| `repo_root` | Enter (Y) | Set to current git checkout |
| Granular layout | `n` + empty overrides | Same derived paths as default layout (correct) |

### UX positives

- Prompts are plain text; easy to automate over PTY.
- `LLM_DEFAULT_DATA_ROOT` is honored in the prompt default.
- Summary block (`wrote …`, paths) is clear before the chain starts.

### Issues / improvements

| ID | Severity | Finding |
|----|----------|---------|
| S1 | Low | `data_root` default in prompt uses **backslashes** on Windows; `llm settings env` emits **forward slashes** (`c:/...`). Inconsistent but functional. |
| S2 | Low | Choosing granular layout (`n`) then accepting all empty overrides is **indistinguishable** from default layout — no hint that nothing changed. |
| S3 | Info | `llm setup --default` **overwrites** existing config at the same `XDG_CONFIG_HOME` path with no warning. |

---

## Phase 2 — Post-settings chain (Questionary + wizards)

### Skipping path (automated)

| Step | Input | Result |
|------|-------|--------|
| Runtime | `n` | `skipped runtime setup` |
| Model URL | Enter (empty) | Skipped pull |
| Create config | Default **Yes** (auto) | Entered config wizard |

### Config wizard — runtime picker (bug)

**Prompt:** `? Pick a runtime (Use arrow keys)` with `llamacpp`, `stub-runtime`, `vllm`.

**Action:** Two `terminal_send_key: down` + `enter` (intended: `stub-runtime`).

**Observed transcript (garbled):**

```text
llamacpp
 » stub-runtime
   stub-runtime
? Pick a runtime vllm
error: no compatible models in registry; `llm model pull <hf-url>` first.
error: config setup aborted
```

**Analysis:**

| ID | Severity | Finding |
|----|----------|---------|
| C1 | **High** | Arrow-key navigation in Questionary **does not render or commit selection reliably** under PTY automation; user may get wrong runtime (`vllm` here) without clear feedback. |
| C2 | Medium | After skip runtime + skip model, **default Yes** on “Create launch config?” pushes users into a wizard that **cannot succeed** without models — predictable failure. Consider default **No** when `model_id` is unset. |
| C3 | Medium | Error `no compatible models in registry` is correct but offers **no link** to re-run model pull or return to setup chain. |

---

## Phase 3 — `llm runtime setup` (preset / stub-runtime)

**Prompts:** Questionary “Preset vs Custom”, then preset list — same arrow-key UI.

**Selection:** `stub-runtime` via down + enter.

**Failure:**

```text
/mnt/c/Private/Projects/local-llm-scaffold/runtimes/stub-runtime/build.sh: line 3: LLM_DATA_ROOT: LLM_DATA_ROOT must be set (run llm init; source .llm-env)
build failed (exit 1)
```

| ID | Severity | Finding |
|----|----------|---------|
| R1 | **High** | On Windows, `run_runtime_bash` → `wsl -e bash -lc …` does not reliably pass **`LLM_DATA_ROOT`** into the script environment (see `src/llm_cli/core/wsl.py`). Blocks preset runtime install during setup. |
| R2 | Low | Error cites **`llm init`** and **`.llm-env`**; current UX is **`llm setup`** + **`eval "$(llm settings env)"`** — stale copy in `build.sh` / error message. |
| R3 | Info | Path shown as `/mnt/c/...` confirms WSL path — expected on Windows, but surprising if user has no WSL installed (would fail earlier). |

---

## Phase 4 — Non-interactive path

`llm setup --default` with isolated `XDG_CONFIG_HOME`:

- Writes config, prints paths, prints **Recommended next steps** (doctor, runtime setup, model pull, config setup, serve).
- **Does not** run `run_setup_chain()` — good for CI/agents.

---

## Environment / install findings (outside setup UI)

| ID | Severity | Finding |
|----|----------|---------|
| E1 | **Critical** | `pip install -e` pointed at **deleted worktree** (`.worktrees/feat-web-dashboard-metrics`). Every `llm` invocation failed with `ModuleNotFoundError: No module named 'llm_cli'` until `pip install -e ".[dev]"` from main. **Deleting worktrees without reinstalling breaks the CLI.** |
| E2 | Medium | Document that worktree removal should be paired with `pip install -e` from the surviving checkout (or `llm update`). |

---

## Recommendations (prioritized)

1. **R1** — Fix WSL env propagation for `LLM_*` in `run_runtime_bash` / `run_repo_bash` (e.g. inline `export LLM_DATA_ROOT=…` in the `bash -lc` script, or `wsl -e env …`).
2. **C1** — Questionary on Windows PTY: offer **numbered/text fallback** when `stdout.isatty()` and TERM is dumb, or accept **typed runtime id** in addition to arrows.
3. **C2** — Chain defaults: if no runtime/model, default “Create launch config?” to **No** or gate with explanation.
4. **E1** — `pip`/editable: warn on `llm doctor` when `.egg-link` / editable path missing; docs for worktree cleanup.
5. **R2** — Update `build.sh` guard message to reference `llm setup` / `llm settings env`.
6. **S2** — When granular layout chosen but all overrides empty, print dim note: “using derived layout”.

---

## Artifacts

| Path | Purpose |
|------|---------|
| `.ux-walkthrough/xdg-config/llm/config.yaml` | First interactive run |
| `.ux-walkthrough/xdg-config-granular/llm/config.yaml` | Granular layout run |
| `.ux-walkthrough/data/` | Isolated data_root (created by `ensure_data_dirs`) |

These paths are gitignored (see `.gitignore`).

---

## Follow-up tests (not run here)

- [ ] Full chain with model pull (network, HF token, disk).
- [ ] `llm config setup` param grid (prompt_toolkit) over PTY.
- [ ] `llm setup` on fresh machine without WSL.
- [ ] Re-run setup when `~/.config/llm/config.yaml` already exists (merge vs overwrite).
- [ ] Warp “Full Terminal Use” vs smart-terminal MCP for same flows.

---

## References

- `src/llm_cli/commands/setup.py` — settings + chain entry
- `src/llm_cli/core/chain.py` — post-settings orchestration
- `src/llm_cli/core/wizards.py` — Questionary vs plain prompts
- `src/llm_cli/core/wsl.py` — Windows bash/WSL invocation

---

## Fix status (`feat/ux-improvements`)

| ID | Status | Implementation |
|----|--------|----------------|
| R1 | **Fixed** | `wsl.py`: inline `export LLM_*` in bash script; WSL paths via `to_wsl_path` on Windows |
| R2 | **Fixed** | `runtimes/stub-runtime/build.sh` error message |
| C1 | **Fixed** | `wizards.py`: plain menus when `LLM_PLAIN_WIZARDS`, `CI`, `CURSOR_AGENT`, or Windows without `WT_SESSION`; `LLM_FORCE_QUESTIONARY` overrides |
| C2 | **Fixed** | `chain.py`: “Create launch config?” defaults to **No** when no model pulled |
| C3 | **Fixed** | `config_cmd.py`: error mentions `llm config setup` after pull |
| S1 | **Fixed** | `setup.py`: `_path_display()` uses forward slashes in prompts and summary |
| S2 | **Fixed** | `setup.py`: dim note when granular layout chosen but no overrides set |
| S3 | **Fixed** | `setup.py`: confirm before overwrite; dim note when `--default` overwrites |
| E1 | **Fixed** | `editable_install.py` + `llm doctor` / `run_quick_checks` |
| E2 | **Fixed** | `docs/DEVELOPMENT.md` worktree + wizard env notes |
| R3 | Doc | Windows runtime scripts require WSL (unchanged); noted in DEVELOPMENT |
