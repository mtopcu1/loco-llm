# loco setup onboarding chain

_Date: 2026-05-21_  
_Status: Draft — awaiting review (rev 4: user-owned deps, hint policy)_  
_Scope: `loco setup` is only the onboarding wizard chain. Machine layout and defaults are established at install; paths are edited via `loco settings`._

## 1. Problem

Users expect **`loco setup`** to mean: walk through the partial wizards until they have a **working launch config** (and optionally a running server).

It must **not**:

- Ask for `data_root`, `repo_root`, or directory layout (that belongs in **`loco settings`**).
- Re-do work **`install.sh`** already performs (create `~/.loco`, write `config.yaml`, seed example configs, create dirs).

After PR #25 + the silent-setup experiment, `loco setup` either printed manual next steps or mixed bootstrap with settings — neither matches the intended product story.

## 2. Decisions

| Topic | Decision |
|-------|----------|
| **Install** | Owns machine bootstrap: `~/.loco` tree, default `config.yaml` (`data_root: <LOCO_HOME>`), seed `configs/*.yaml`, venv/symlink. |
| **`loco setup`** | **Only** `run_setup_chain()` — runtime → model → config → optional serve → optional dashboard. |
| **Paths / defaults** | Written at install; changed later with **`loco settings show` / `loco settings edit`**. |
| **`loco setup --default`** | **Removed** from product surface (install.sh does not call it). |
| **Dependencies** | **User-owned** — no doctor blocking gate in setup, no `doctor --install`, no apt/brew auto-run. Doctor and `_pre_flight` print hints only. |
| **Partial wizards** | Unchanged commands; chain delegates to them (`runtime setup`, model pull, `config setup`, `serve`, `dashboard install`). |

## 3. Responsibility split

```text
install.sh
  ├── LOCO_HOME dirs + config.yaml (defaults)
  ├── seed configs from install checkout
  └── (no loco setup subprocess)

loco setup                    → onboarding chain only
loco settings …               → data_root, repo_root, dir overrides
loco doctor                     → verify environment
```

## 4. `loco setup` behavior

**Entry:** `loco setup` (no flags).

**Prerequisites** (fail fast with clear message if missing):

- `{LOCO_HOME}/config.yaml` exists and resolves `data_root`.
- `ensure_data_dirs` already satisfied (normally true after install).

If prerequisites fail:

```text
error: data home not initialized — run the installer first:
  curl -fsSL …/install.sh | bash
Paths can be changed later with: loco settings edit data_root
```

**Then:** `run_setup_chain()` exactly as in `core/chain.py` today:

1. Install/register runtime? (default Yes) → `interactive_runtime_setup()`
2. Hugging Face URL (empty = skip) → model pull flow
3. Create launch config? (default Yes if model pulled) → `do_config_setup()`
4. Serve in background? (default Yes if config created)
5. Install dashboard? (default No)

**Exit:** non-zero on hard failure or config abort; skips are fine.

**Branding:** user-facing strings in chain use `loco`, not `loco`.

**No** bootstrap, **no** seeding, **no** summary of paths, **no** “recommended next steps” list at end of setup (chain already prints next action).

## 5. Install script

`scripts/install.sh` already:

- `mkdir` `~/.loco/{configs,models,runtimes,cache,state,user,install}`
- Writes `config.yaml` if missing (`data_root: $LOCO_HOME`)
- Seeds `configs/*.yaml` from install checkout

**Change:** remove the block that runs `loco setup --default` (bootstrap moves entirely into the shell script; no duplicate CLI bootstrap).

**Post-install message** (example):

```text
next: loco setup    # first-run wizard (runtime, model, config)
      loco doctor   # verify environment
```

## 6. Settings CLI

Defaults live in `~/.loco/config.yaml` after install. Users change them anytime:

```bash
loco settings show
loco settings edit data_root
loco settings edit repo_root    # dev checkout override
```

Setup never reads cwd for `repo_root` and never prompts for layout.

## 7. Developer / test bootstrap

Editable installs and tests still need an isolated data home without running the full installer:

- **Tests:** existing `loco_data_isolated` autouse fixture + explicit `save_settings` in integration tests (unchanged pattern).
- **Dev:** `scripts/install-dev.sh` or docs: run installer once, or manually create `config.yaml` + dirs — not `loco setup`.

Optional future: hidden `loco internal-bootstrap` for tests only — **out of scope** unless tests need it; prefer fixture + `save_settings`.

## 8. Command surface

| Command | Purpose |
|---------|---------|
| `loco setup` | Onboarding wizard chain only |
| `loco settings …` | Machine paths and overrides |
| `install.sh` | Software + data home defaults |

Remove `--default` from `setup` Typer options.

Update `main.py` help:  
`setup` — “First-run wizard: runtime, model, launch config, optional serve.”

## 9. Testing

| Test | Expectation |
|------|-------------|
| `loco setup` with prerequisites met | Invokes `run_setup_chain` (mocked) |
| `loco setup` without `config.yaml` | Exit ≠ 0, message mentions installer |
| `test_setup_*` bootstrap tests | **Move** to install integration tests or delete; replace with prerequisite + chain tests |
| `test_setup_default_skips_chain` | **Remove** or replace with install.sh test |
| Chain not invoked from `--default` | N/A once flag removed |

## 10. Non-goals

- Typer path wizard inside setup.
- `loco setup --default` as user-facing bootstrap.
- QuickStart vs Advanced onboarding modes.
- Renaming `loco setup` to `loco onboard`.

## 11. Dependencies and hints (not auto-install)

### 11.1 Behavior

| Piece | Behavior |
|-------|----------|
| `loco doctor` | Standalone report: universal `requirements.yaml` + optional runtime/dashboard scopes. Prints `install_hint` text only — **no** `--install`, no subprocess execution. |
| `_pre_flight()` | On preset install, checks runtime `requires:`; fails with hints — user installs manually. |
| `loco setup` | **No** doctor gate. Optional soft tip in install footer: run `loco doctor` on a new machine. |

Users fix the machine themselves; doctor/setup only guide.

### 11.2 `install_hint` authoring policy

Hints are free-form markdown-ish text shown in doctor tables and pre-flight errors. **Do not parse or execute them.**

| Case | Hint should say |
|------|-----------------|
| Tool on PyPI | `pip install …` first, then OS package or upstream URL if pip is insufficient. |
| OS packages | `apt` / `dnf` / `brew` / `xcode-select` as secondary lines when common. |
| Drivers / CUDA / Node | Official download or docs URL (first or alongside OS commands). |
| Multi-step | First line = quickest path; following lines = alternatives. |

Examples (in repo):

- `hf-cli` → `pip install -U "huggingface_hub[cli]"` + HF CLI docs URL.
- `cmake` (runtime) → `pip install -U "cmake>=3.16"` + apt + https://cmake.org/download/
- `nvcc` → https://developer.nvidia.com/cuda-downloads
- `cuda-driver` → NVIDIA driver download page

Regenerate `requirements.md` via `loco doctor render-requirements` when `requirements.yaml` changes.

### 11.3 Rejected (non-goals)

- Blocking doctor loop inside `loco setup` or `interactive_runtime_setup()`.
- `doctor --install` and structured `install:` argv recipes in YAML.
- Parsing `install_hint` to run shell commands.

## 12. Verification

- After `install.sh`: `loco setup` runs the onboarding chain (no bootstrap prompts).
- `loco doctor` shows improved hints; user installs manually.
- `loco settings edit data_root` unchanged.
- `install.sh` does not invoke `loco setup`; footer points to `loco setup` and `loco doctor`.
