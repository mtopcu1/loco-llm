# loco-llm Hermes layout and branding

_Date: 2026-05-20_
_Status: Approved — implementing on feat/ux-improvements_
_Scope: Nested install layout (Hermes-style), CLI rename `llm` → `loco`, data home `~/.loco`._

## 1. Purpose

End users get a single mental model: **`loco`** is the command, **`~/.loco`** is where their data lives, **`~/.loco/install`** is the managed git checkout. No mixed `llm` / `loco-llm` / `~/.config/llm` paths.

## 2. Decisions

| Topic | Decision |
|-------|----------|
| CLI command | **`loco`** (replaces `llm` on `$PATH`) |
| Data home | **`~/.loco`** (replaces `~/.loco-llm` and `~/.config/llm/config.yaml`) |
| Install root | **`~/.loco/install`** (git clone + `.venv`) |
| Settings file | **`~/.loco/config.yaml`** |
| Launch configs | **`~/.loco/configs/*.yaml`** only (repo examples seeded once at install) |
| Env: data home | **`LOCO_HOME`** (default `~/.loco`) |
| Env: install | **`LOCO_INSTALL`** (default `$LOCO_HOME/install`) |
| Deprecated env | `LOCO_LLM_DATA`, `LOCO_LLM_HOME` — read as fallback one release, then remove |
| Python package | Keep `loco-llm-cli` / `llm_cli` internally (PyPI name unchanged) |
| Migration | None in-tool; maintainer reinstalls (`rm -rf ~/.loco-llm` + fresh install) |

## 3. Layout

```text
~/.loco/                          ← LOCO_HOME
├── config.yaml                   ← machine settings
├── configs/*.yaml                ← launch units (canonical)
├── models/ runtimes/ cache/ state/
├── user/runtimes/                ← optional custom recipes
└── install/                      ← LOCO_INSTALL
    ├── .git/ .venv/ src/
    ├── runtimes/ benchmarks/     ← upstream recipes
    └── configs/                  ← examples → copied to ../configs/ once

~/.local/bin/loco  →  ~/.loco/install/.venv/bin/loco
```

## 4. Install flow (`scripts/install.sh`)

1. Resolve `LOCO_HOME` (default `~/.loco`), `LOCO_INSTALL` (default `$LOCO_HOME/install`).
2. Clone/update git at `LOCO_INSTALL`, checkout tag, `uv pip install -e .`.
3. Symlink `~/.local/bin/loco`.
4. `mkdir` data-home dirs; write `config.yaml` if missing (`data_root: <LOCO_HOME>`).
5. Seed `configs/*.yaml` from install (skip existing).
6. Run `loco setup --default` when TTY available (`< /dev/tty` for piped curl).

Flags: `--data-home`, `--dir` (install), `--tag`, `--branch`, `--skip-setup`.

## 5. Runtime resolution

| Function | Order |
|----------|--------|
| `data_home()` | `LOCO_HOME` → `config.yaml` `data_root` → `~/.loco` |
| `install_root()` | `LOCO_INSTALL` → `repo_root` (dev) → `$data_home/install/.git` → package git toplevel |
| `settings_path()` | `data_home() / config.yaml` |
| `discover_configs_merged()` | `data_home()/configs` only |
| `discover_runtimes_merged()` | install recipes + `user/runtimes` overrides |
| `state_root()` | always `data_root` |

## 6. Setup (`loco setup`)

- Writes/refreshes `config.yaml`; `ensure_data_dirs()`; optional `seed_configs_from_install()`.
- **No** post-setup chain (runtime → model → config → serve).
- `--default`: non-interactive; honors `LOCO_HOME` when set (installer/tests).
- Interactive: data_root prompt only; optional dev `repo_root` when cwd is a git checkout.

## 7. Update (`loco update`)

Unchanged semantics: git fetch/checkout on **install root** only; never touches `~/.loco/configs/` or artifacts.

## 8. Developer workflow

- Editable install from clone; `repo_root` in `config.yaml` points at dev tree.
- Invoke via `uv run loco` or `loco-dev` suffix if documented in CONTRIBUTING.
- `LOCO_INSTALL` not required when `repo_root` is set.

## 9. Non-goals

- No `llm` shim on `$PATH` after this change.
- No automatic migration from `~/.loco-llm` or `~/.config/llm`.
- No rename of Python module `llm_cli` in this pass.
- No sparse checkout / tarball distribution (future).

## 10. Documentation updates

- `docs/INSTALLATION.md`, `docs/ARCHITECTURE.md`, `docs/repo-conventions.md`, `README.md`
- Reinstall section: remove `~/.loco-llm`, `~/.local/bin/llm`

## 11. Verification

- `pytest tests/` (except `tests/tui` on Windows)
- Manual: curl install → `loco doctor` → `loco list configs`
