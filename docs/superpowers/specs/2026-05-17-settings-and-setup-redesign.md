# LocalLLM Settings & Setup Redesign

_Date: 2026-05-17_
_Status: Approved by user, ready for implementation planning_

## 1. Purpose

Replace the current `paths.yaml` + `llm init` flow with a clean separation between **machine-local settings** (where data lives on this machine) and **repo content** (runtimes, models, launch configs, benchmarks). Introduce a guided first-time setup and an explicit settings command surface so the user never has to hand-edit a YAML file or remember to re-run `init`.

## 2. Problems with the current design

- **Per-machine state lives in a committed file.** `paths.yaml` is tracked in git; editing `data_root` for the local machine produces a permanent diff the user has to remember not to commit.
- **No guided onboarding.** After `./install.sh`, the user has to know to edit `paths.yaml`, then run `llm init`, then optionally re-edit and re-init.
- **Two-step apply.** `llm init` regenerates `.llm-env` from `paths.yaml`. The two-step shape is leaky — any settings change requires remembering to run init.
- **Naming collision risk.** The proposed `llm config edit data_root` would collide with the existing `llm config show/validate` namespace, which already means **launch configurations** (`configs/{id}.yaml`).

## 3. Goals

- **Machine settings live outside the repo** at an XDG-standard location (`~/.config/llm/config.yaml`).
- **First-time setup is a single guided command** (`llm setup`) that is invoked automatically by `install.sh` when no settings file exists.
- **Two namespaces stay distinct**: `llm settings ...` for user-level settings, `llm config ...` for repo launch configs.
- **No materialized env file.** Shell env vars are produced on demand via `eval "$(llm settings env)"`, so there is no stale file to manage.
- **Granular control when needed.** Default flow stores only `data_root`; advanced users can override `runtimes_dir`/`models_dir`/`cache_dir` individually.

## 4. Non-goals

- Not a multi-profile system. One settings file per user is enough.
- Not a remote config system. No fetching settings from a server.
- Not a migration tool for users with existing `paths.yaml`. (User is the sole consumer; the migration is a one-time manual step.)
- `serve` / `start` / `stop` / `bench` lifecycle commands are out of scope for this spec — they remain on the broader roadmap.

## 5. Architecture

### 5.1 Settings file

**Location:** `${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml`.

**Schema (dir keys optional, `data_root` and `repo_root` required):**

```yaml
data_root: ~/llm
repo_root: /mnt/c/Private/Projects/LocalLLM
# Optional explicit overrides. If a key is absent, the CLI derives it as
# ${data_root}/<name> at runtime.
# runtimes_dir: /mnt/d/runtimes
# models_dir:   /mnt/e/models
# cache_dir:    ~/llm/cache
```

**Resolution rules:**

- `data_root` is required; the built-in default is `~/llm`.
- `repo_root` is required; no built-in default — `llm setup` records it from `cwd` (which is the repo root when `install.sh` invokes it).
- `runtimes_dir` / `models_dir` / `cache_dir` are stored only when the user has explicitly overridden them. Otherwise they're computed at read time from `data_root` (joining `runtimes`, `models`, and `cache` respectively).
- `~` is expanded to the user's home at resolution time, not at write time (so a settings file moved between machines still works).
- The CLI exposes a resolved, fully-populated view internally (`Settings` dataclass) — `data_root`, `repo_root`, `runtimes_dir`, `models_dir`, `cache_dir`, all as absolute `Path` objects.

### 5.2 Repo location

`paths.yaml` is **removed from the repo**. The repo no longer carries any per-machine state.

Repo discovery is trivial: `repo_root` is read from `~/.config/llm/config.yaml`. There is **no env-var override and no walk-up heuristic**. `llm setup` records `repo_root = cwd` automatically (which is the repo when `install.sh` invokes it). `llm settings edit repo_root` is the escape hatch if the clone is ever moved.

If `repo_root` is missing or points at a directory that doesn't exist, repo-aware commands (`list`, `build`, `pull`, `config validate`, `doctor`, `specs`) error with: `repo_root is not configured; run \`llm setup\` from inside the repo`.

### 5.3 Env injection for bash scripts

The CLI is the only thing that runs `runtimes/{id}/build.sh`, `models/{id}/pull.sh`, etc. When it spawns bash, it **injects the resolved env vars directly** into the subprocess environment:

| Env var | Source |
|---|---|
| `LLM_DATA_ROOT` | `Settings.data_root` |
| `LLM_REPO_ROOT` | `Settings.repo_root` |
| `LLM_RUNTIMES` | `Settings.runtimes_dir` |
| `LLM_MODELS` | `Settings.models_dir` |
| `LLM_CACHE` | `Settings.cache_dir` |

No `.llm-env` file is written. For manual shell use, `llm settings env` prints `export KEY=value` lines suitable for `eval`:

```bash
eval "$(llm settings env)"
bash runtimes/stub-runtime/build.sh
```

This is the same idiom as `direnv hook`, `starship init`, etc. — stateless, always current, no gitignore needed.

## 6. Command surface

### 6.1 New commands

| Command | Behavior |
|---|---|
| `llm setup` | Records `repo_root = cwd` silently (no prompt). Then two-phase interactive walkthrough: (1) prompt for `data_root` (default `~/llm`); (2) prompt "Use default subdirectory layout under data_root? [Y/n]" — if **Y**, store only `data_root` + `repo_root`; if **n**, prompt for each of `runtimes_dir`, `models_dir`, `cache_dir` with the derived default shown in brackets, empty answer keeps the key derived. Write the settings file (creating `~/.config/llm/` as needed), `mkdir -p` each resolved data dir, print a summary. |
| `llm setup --default` | Non-interactive. Records `repo_root = cwd` and `data_root = ~/llm`, creates dirs, prints the resolved view. Used by automation and tests. |
| `llm settings show` | Print the stored file path, the raw stored contents, and the resolved effective view (with derived keys filled in). |
| `llm settings env` | Print `export LLM_*=...` lines for the resolved view. No newline-quoting surprises; values are shell-escaped. Designed for `eval "$(llm settings env)"`. |
| `llm settings edit <key>` | Interactive: prompt for one key with the current stored (or derived) value as the default. Validate, write the file, `mkdir -p` the new target if it's a dir key. |
| `llm settings edit <key> --default` | Reset that key to its built-in default. For `data_root`, that's `~/llm`. For the three dir keys, "default" means **removed from the file** so it goes back to being derived from `data_root`. `repo_root` has no built-in default and rejects `--default` with a clear error (use plain `llm settings edit repo_root` to set a new path). |

### 6.2 Commands kept verbatim

`llm config show <id>`, `llm config validate`, `llm list`, `llm build`, `llm pull`, `llm doctor`, `llm doctor render-requirements`, `llm specs`, `llm specs --check`, `llm specs --print`.

These all switch from reading `paths.yaml` to reading the resolved `Settings`, but their CLI surface is unchanged.

### 6.3 Commands removed

- **`llm init`** — its work (create data-root subdirectories, write `.llm-env`) is absorbed by `setup`. The subdirectory creation moves into `setup` / `settings edit`. The `.llm-env` file goes away entirely.

### 6.4 Valid keys today

`data_root`, `repo_root`, `runtimes_dir`, `models_dir`, `cache_dir`. Unknown keys passed to `llm settings edit` produce a clear error listing the known keys. (This list is the registry that drives `setup` too.)

## 7. install.sh changes

End of `install.sh` (in WSL) — note the explicit `cd` so `setup` records `repo_root` correctly:

```bash
if [ -z "${LLM_SKIP_SETUP:-}" ] && [ ! -f "${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml" ]; then
  ( cd "$REPO_ROOT" && "$venv_dir/bin/llm" setup )
fi
```

- Auto-runs `llm setup` interactively on first install.
- Skippable with `LLM_SKIP_SETUP=1` (for CI / scripted setups).
- A re-install with an existing settings file is a no-op (does not overwrite). To rewrite, the user runs `llm setup` (or `llm settings edit <key>`) manually.

## 8. File / module layout (concrete)

| Path | Role |
|---|---|
| `src/llm_cli/core/settings.py` | `Settings` dataclass, `load_settings()`, `save_settings()`, `resolve(settings)` → fully-populated `Settings`, `default_settings()`, `settings_path()` (XDG-aware), `KEY_REGISTRY` describing each key (default, prompt text, validator). |
| `src/llm_cli/core/repo.py` | Shrinks to `repo_root() -> Path` that reads resolved `Settings.repo_root`. Raises a clear error if missing. No env-var override, no walk-up. |
| `src/llm_cli/core/wsl.py` | `run_repo_bash()` accepts a resolved `Settings` and injects `LLM_DATA_ROOT` / `LLM_REPO_ROOT` / `LLM_RUNTIMES` / `LLM_MODELS` / `LLM_CACHE` into the subprocess env. The `source .llm-env` shell prelude is removed. |
| `src/llm_cli/commands/setup.py` | `llm setup` command (interactive + `--default`). |
| `src/llm_cli/commands/settings_cmd.py` | `llm settings show / env / edit` Typer sub-app. |
| `src/llm_cli/commands/init.py` | **Deleted.** |
| `src/llm_cli/commands/artifacts.py` | Updated: pass `Settings` into `run_repo_bash`. |
| `src/llm_cli/commands/specs.py` | Updated: read `data_root` from resolved `Settings` instead of `paths.yaml`. |
| `src/llm_cli/commands/doctor.py` | Unchanged. |
| `src/llm_cli/core/paths.py` | **Deleted** (its job is now in `settings.py`). |
| `paths.yaml` (repo root) | **Deleted**. |
| `install.sh` | Adds the auto-`setup` block above. |

## 9. Backwards-compat / migration

User is the sole consumer; no compat shim is needed. The migration is:

1. `git pull` this change.
2. Reinstall (`./install.sh`) — auto-runs `llm setup` because no settings file exists.
3. Old `.llm-env` in the repo can be deleted; it will be added to `.gitignore` defensively (it should already be there).

## 10. Tests

New / updated:

- **`tests/unit/test_settings.py`** — defaults, derivation rules, `~` expansion, save/load round-trip, XDG honored, unknown keys error, `repo_root` required (missing → clear error).
- **`tests/unit/test_repo.py`** — `repo_root()` reads from settings; raises a clear error if `repo_root` is missing. No env-var override is tested (it doesn't exist anymore).
- **`tests/unit/test_wsl.py`** — `run_repo_bash` injects the five `LLM_*` env vars from a resolved `Settings` and no longer sources `.llm-env`.
- **`tests/integration/test_cli_setup.py`** — `llm setup --default` is non-interactive, records `repo_root = cwd`, writes the expected file + creates data dirs; `llm settings show` reflects both stored and resolved; `llm settings env` round-trips through bash `eval`; `llm settings edit data_root --default` resets; `llm settings edit runtimes_dir --default` removes the override; `llm settings edit repo_root --default` errors clearly.
- **`tests/integration/test_cli_milestone2.py`** — switched to redirect `XDG_CONFIG_HOME=tmp_path/cfg` and prewrite a settings file pointing `repo_root` at the test repo fixture. `LLM_REPO_ROOT` is no longer used anywhere.
- **Removed:** any test that asserted `paths.yaml` / `.llm-env` / `LLM_REPO_ROOT` behavior. The Milestone-1 `llm init` tests are deleted with the command.

## 11. Documentation updates

- **`docs/repo-conventions.md`** — replace the `paths.yaml` row with a `~/.config/llm/config.yaml` row; mention `llm settings env`.
- **`docs/add-a-runtime.md`** / **`add-a-model.md`** — replace references to `llm init` / `.llm-env` with `llm settings env` (manual case) or "just run `llm build` / `llm pull`" (managed case).
- **`README.md`** — update the CLI table: drop `llm init`, add `llm setup` / `llm settings ...`. Replace the "Getting started" block with the new install → setup → doctor flow.
- **Design spec** (`2026-05-15-localllm-scaffolding-design.md`) — add a short pointer at the top: "Superseded sections about `paths.yaml` / `llm init`: see 2026-05-17-settings-and-setup-redesign.md."

## 12. Open questions / deferred

- A non-interactive `llm settings edit <key> <value>` setter (no flag): not needed yet; `--default` + interactive `edit` covers today's flow. Add later if scripting needs it.
- A `--config-path` global flag to override the settings file location: not needed; `XDG_CONFIG_HOME` already covers tests and unusual setups.
- Validation of `data_root` writability: `setup` does `mkdir -p` which surfaces permission errors clearly; no extra validation layer.

## 13. Implementation order (preview)

This is left to the implementation plan, but the natural order is:

1. Introduce `core/settings.py` + tests; leave `paths.py` alone.
2. Add `llm setup` and `llm settings ...` commands; wire into `main.py`.
3. Migrate `repo.py` / `wsl.py` / `artifacts.py` / `specs.py` to use `Settings`; drop `paths.yaml` + `core/paths.py` + `llm init`.
4. Update `install.sh` and docs.
5. Smoke test in WSL: install → setup → list → build/pull → eval-env round trip.
