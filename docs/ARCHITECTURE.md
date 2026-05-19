# Architecture

High-level shape of LocalLLM. For scaffolding design (runtimes, configs, lifecycle), see
[`docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`](superpowers/specs/2026-05-15-localllm-scaffolding-design.md).

## Distribution

The product ships as a **single git checkout** — not a PyPI wheel plus a separate asset bundle.

```
~/.loco-llm/                      ← LOCO_LLM_HOME (default)
├── .git/                         ← origin: github.com/mtopcu1/loco-llm
├── .venv/                        ← uv venv, editable install
│   └── bin/llm
├── src/llm_cli/                  ← Typer CLI
├── runtimes/ configs/ benchmarks/ ← ship with the tag; no side channel
└── pyproject.toml

~/.local/bin/llm  →  ~/.loco-llm/.venv/bin/llm

~/.config/localllm/settings.yaml         ← user settings
~/.local/share/localllm/                 ← models, builds, lifecycle state
```

| Concern | Mechanism |
|---------|-----------|
| First install | `curl …/scripts/install.sh \| bash` clones, checks out latest `v*.*.*` tag, `uv pip install -e .` |
| Upgrade | `llm update` → `git fetch`, checkout latest tag (or `--branch` / `--tag`) |
| Release artifact | Git tag + GitHub Release CHANGELOG only |
| Resolve install root | `scaffold_root()` → `$LOCO_LLM_HOME` → settings `repo_root` → git toplevel of package |

`scaffold_root()` is the install root; there is no second "scaffold directory" or tarball layer.

### Install / update scripts

- **`scripts/install.sh`** — public curl entry; documented in [INSTALLATION.md](INSTALLATION.md).
- **Root `install.sh`** — thin wrapper that execs `scripts/install.sh` for anyone running `./install.sh` from a clone.

### Off-tag operation

`llm update --branch` is for hotfixes. Bare `llm update` **re-anchors** to the latest semver tag. `llm doctor` and `llm --version` surface when HEAD is not an exact tag.

## CLI layers

| Layer | Role |
|-------|------|
| `src/llm_cli/commands/` | Typer commands (`setup`, `serve`, `update`, …) |
| `src/llm_cli/core/` | Settings, scaffold root, lifecycle, registry |
| Repo `runtimes/` | Manifests + build/serve scripts (discovered from install root) |
| User data dir | Models, installed runtimes, `running.json`, logs |

## CI and release (summary)

Two workflows: **`ci.yml`** (PR tests) and **`release-please.yml`** (tagging only). See [CI.md](CI.md) and [RELEASE.md](RELEASE.md).
