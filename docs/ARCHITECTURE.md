# Architecture

High-level shape of loco-llm. For scaffolding design (runtimes, configs, lifecycle), see
[`docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`](superpowers/specs/2026-05-15-localllm-scaffolding-design.md).

Branding and layout: [`docs/superpowers/specs/2026-05-20-hermes-layout-and-branding-design.md`](superpowers/specs/2026-05-20-hermes-layout-and-branding-design.md).

## Distribution (Hermes-style nested layout)

```text
~/.loco/                          ← LOCO_HOME (default)
├── config.yaml                   ← machine settings (paths)
├── configs/*.yaml                ← launch units (canonical)
├── models/ runtimes/ cache/ state/
└── install/                      ← LOCO_INSTALL (git clone)
    ├── .git/ .venv/ src/
    ├── runtimes/ configs/ benchmarks/

~/.local/bin/loco  →  ~/.loco/install/.venv/bin/loco
```

| Concern | Mechanism |
|---------|-----------|
| CLI | **`loco`** on `$PATH` (`[project.scripts]` in `pyproject.toml`) |
| First install | `install.sh` clones to `$LOCO_HOME/install`, seeds `config.yaml` + `configs/` |
| Upgrade | `loco update` → git + `uv pip install -e .` on **install/** only |
| Launch configs | Read/write `{LOCO_HOME}/configs/` only |
| Resolve install | `install_root()` → `$LOCO_INSTALL` → `repo_root` (dev) → `{data_home}/install/.git` |
| Resolve data | `data_home()` → `$LOCO_HOME` → `config.yaml` `data_root` → `~/.loco` |

`scaffold_root()` is an alias for `install_root()`.

### Install / update scripts

- **`scripts/install.sh`** — public curl entry; documented in [INSTALLATION.md](INSTALLATION.md).

### Off-tag operation

`loco update --branch` switches to a branch. Bare `loco update` **refreshes the current ref** (branch tip or latest tag). Use `loco update --stable` to switch to the latest semver tag.

## CLI layers

| Layer | Role |
|-------|------|
| `src/llm_cli/commands/` | Typer commands (`setup`, `serve`, `update`, …) |
| `src/llm_cli/core/` | Settings, paths, lifecycle, registry |
| `install/runtimes/` | Manifests + build/serve scripts (read-only recipes) |
| Data home | Configs, models, installed runtimes, `state/` |

## CI and release (summary)

Two workflows: **`ci.yml`** (PR tests) and **`release-please.yml`** (tagging only). See [CI.md](CI.md) and [RELEASE.md](RELEASE.md).
