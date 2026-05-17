# LocalLLM

Personal control plane for local LLM runtimes — manage runtime configurations,
benchmark them, and pin one as a "daily driver" that serves an OpenAI-compatible
endpoint.

This repo contains **text only** — manifests, configs, scripts, benchmark
results. Runtime source trees and model weights live in WSL2's native
filesystem under `~/llm/` (configurable via `llm setup` / `llm settings ...`).

## Getting started (first time)

Inside WSL2:

```bash
# 1. Verify external prerequisites
cat requirements.md
# (or after install:) llm doctor

# 2. Install the CLI into a venv and run first-time setup
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # if not already

# 3. Inspect settings (settings live at ~/.config/llm/config.yaml)
llm settings show

# 4. Document the machine
llm specs
```

## Layout

| Path | What it holds |
|---|---|
| `runtimes/{id}/` | Manifest + build/serve/healthcheck scripts for one runtime |
| `models/{id}/` | Manifest + pull script for one model (no weights — those live in `~/llm/models/`) |
| `configs/{id}.yaml` | One launch unit (runtime + model + flags) |
| `benchmarks/{id}/` | Wrapper around an existing benchmark tool, plus committed results |
| `state/` | Pinned daily driver, currently-running processes, history |
| `docs/` | HOWTOs and reference notes |
| `src/llm_cli/` | The Python CLI implementation |

See [`docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`](docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
for the full design.

## CLI commands (Milestone 1–2)

| Command | Purpose |
|---|---|
| `llm setup` | Interactive first-time configurator. Writes `~/.config/llm/config.yaml`, creates data-root subdirectories. Re-runnable. |
| `llm setup --default` | Non-interactive: use built-in defaults for every key. |
| `llm settings show` | Print settings file path, stored contents, and resolved view. |
| `llm settings env` | Print `export LLM_*=...` lines for `eval "$(llm settings env)"`. |
| `llm settings edit <key>` | Interactive prompt to update one key. |
| `llm settings edit <key> --default` | Reset key to its built-in default (`data_root`) or remove the override (`runtimes_dir`/`models_dir`/`cache_dir`). |
| `llm specs` | Regenerate the auto block in `specs.md` |
| `llm specs --check` | Exit nonzero if `specs.md` differs from current detection |
| `llm specs --print` | Print detection without writing |
| `llm doctor` | Run all checks from `requirements.yaml` |
| `llm doctor render-requirements` | Regenerate `requirements.md` from `requirements.yaml` |
| `llm list` | List runtimes, models, configs, and benchmarks |
| `llm config show <id>` | Print a single launch config (with `${data_root}` expanded in `serve.env`) |
| `llm config validate` | Validate every `configs/*.yaml` against manifests and script layout |
| `llm build <runtime-id>` | Run `runtimes/<id>/build.sh` via WSL bash with `LLM_*` env injected |
| `llm pull <model-id>` | Run `models/<id>/pull.sh` via WSL bash with `LLM_*` env injected |

Future milestones add `llm status / start / stop / switch / default / bench / results`.

## Discipline

When you change a workflow:

- Update the corresponding `docs/add-a-*.md` HOWTO **in the same commit** (or immediately after).
- If you add a new external dependency, update `requirements.yaml` and regenerate `requirements.md` in the same commit.
- A HOWTO that's more than two weeks stale relative to actual practice is a bug.

See the [documentation index](docs/README.md).
