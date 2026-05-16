# LocalLLM

Personal control plane for local LLM runtimes — manage runtime configurations,
benchmark them, and pin one as a "daily driver" that serves an OpenAI-compatible
endpoint.

This repo contains **text only** — manifests, configs, scripts, benchmark
results. Runtime source trees and model weights live in WSL2's native
filesystem under `~/llm/` (configurable via `paths.yaml`).

## Getting started (first time)

Inside WSL2:

```bash
# 1. Verify external prerequisites you'll need
cat requirements.md     # human-readable list
# (or after install:) llm doctor render-requirements && cat requirements.md

# 2. Install the CLI into a venv at ~/llm/.cli-venv/
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # if not already

# 3. Initialize data-root subdirectories
llm init

# 4. Document the machine
llm specs

# 5. Verify external requirements
llm doctor
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

## CLI commands (Milestone 1 — current)

| Command | Purpose |
|---|---|
| `llm init` | Read `paths.yaml`, create data-root subdirectories, write `.llm-env` |
| `llm specs` | Regenerate the auto block in `specs.md` |
| `llm specs --check` | Exit nonzero if `specs.md` differs from current detection |
| `llm specs --print` | Print detection without writing |
| `llm doctor` | Run all checks from `requirements.yaml` |
| `llm doctor render-requirements` | Regenerate `requirements.md` from `requirements.yaml` |

Future milestones add `llm list / status / build / pull / start / stop / switch / default / bench / results`.

## Discipline

When you change a workflow:

- Update the corresponding `docs/add-a-*.md` HOWTO **in the same commit** (once those files exist).
- If you add a new external dependency, update `requirements.yaml` and regenerate `requirements.md` in the same commit.
- A HOWTO that's more than two weeks stale relative to actual practice is a bug.
