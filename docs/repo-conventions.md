# Repository conventions

This document matches the **current** repo layout and CLI behavior (Milestone 2).
Future commands (`start`, `bench`, …) will extend the same contracts.

## Root files

| File | Role |
|---|---|
| `~/.config/llm/config.yaml` | Per-machine settings (managed via `llm settings ...`); not in the repo |
| `requirements.yaml` | External prerequisites for `llm doctor` |
| `requirements.md` | Regenerated via `llm doctor render-requirements` |
| `specs.md` | Host/GPU/WSL snapshot via `llm specs` |

## Settings vs configs

Two namespaces, intentionally separate:

- **`llm settings ...`** edits `~/.config/llm/config.yaml` (where data lives on this machine, where the repo is, etc.).
- **`llm config show/validate`** operates on `configs/*.yaml` (launch units pairing a runtime + model + serve block).

For manual bash, `eval "$(llm settings env)"` injects `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE` into the current shell.

## Directory layout

| Path | Contains |
|---|---|
| `runtimes/{id}/` | `manifest.yaml`, `build.sh`, `serve.sh`, `healthcheck.sh`, `README.md` |
| `models/{id}/` | `manifest.yaml`, `pull.sh`, `README.md` |
| `configs/{config-id}.yaml` | One launch unit (runtime + model + `serve` block) |
| `benchmarks/{id}/` | `bench.yaml`, `run.sh`, `README.md`, optional `results/` |
| `src/llm_cli/` | Python Typer CLI |
| `docs/` | HOWTOs and reference |

Heavy artifacts (cloned runtimes, venvs, weights) live under the **data root** from `~/.config/llm/config.yaml` (typically `~/llm/` in WSL), not under the git checkout on `/mnt/c/...`.

## Naming

- **Runtime and model IDs** — use lowercase and hyphens (e.g. `vllm-cuda`, `qwen2-7b-q5km`). They must match the directory name unless `manifest.yaml` sets `id` explicitly.
- **Config files** — prefer `{runtime-id}__{model-id}__{preset}.yaml` (double underscore between the three parts). The optional top-level `id:` in YAML should match the filename stem; `llm config validate` checks that.

## CLI discovery

- **`llm list`** — scans `runtimes/*/manifest.yaml`, `models/*/manifest.yaml`, `configs/*.yaml`, `benchmarks/*/bench.yaml`.
- **`llm config validate`** — for each config: runtime and model exist, runtime has the three scripts, model has `pull.sh`, `serve.host` / `serve.port` present, and settings resolve. Optional `readiness` must be a mapping if present.

## Git: what to commit

- Commit manifests, configs, scripts, benchmark metadata, and (per design) small benchmark results under `results/` once the benchmark workflow is wired.
- Do **not** commit machine-local settings, generated env files, or live state files like `state/running.json` when those exist (see design spec for the full gitignore story).

## Stub packages

`stub-runtime`, `stub-model`, `stub-bench`, and `configs/stub-runtime__stub-model__default.yaml` are minimal smoke examples; replace them with real entries or add siblings alongside them.
