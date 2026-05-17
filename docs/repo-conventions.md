# Repository conventions

This document matches the **current** repo layout and CLI behavior through lifecycle commands (`serve`, `stop`, …).
Future milestones (`bench`, …) will extend the same contracts.

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
| `configs/{config-id}.yaml` | One launch unit (runtime + optional model + `serve` block) |
| `benchmarks/{id}/` | `bench.yaml`, `run.sh`, `README.md`, optional `results/` |
| `state/` | **Not committed.** `running.json`, `history.jsonl`, per-session logs under `logs/` — see `docs/lifecycle.md` |
| `src/llm_cli/` | Python Typer CLI |
| `docs/` | HOWTOs and reference |

Heavy artifacts (cloned runtimes, venvs, weights) live under the **data root** from `~/.config/llm/config.yaml` (typically `~/llm/` in WSL), not under the git checkout on `/mnt/c/...`.

Models are **not** kept in the repo. They live per-machine in `$LLM_MODELS/registry.json` (one JSON file under the data root) and `$LLM_MODELS/<id>/` (weights, symlinked or downloaded by `llm model pull` / `llm model add`). See [`add-a-model.md`](add-a-model.md).

## Naming

- **Runtime IDs** — lowercase and hyphens (e.g. `vllm-cuda`); must match the directory name unless `manifest.yaml` sets `id` explicitly.
- **Model IDs** — also lowercase and hyphens, derived automatically by `llm model pull` from the HF repo + (for GGUF) the quant tag (e.g. `unsloth-qwen3.6-235b-a22b__ud-q4-k-xl`). Override with `--id` if you need to.
- **Config files** — prefer `{runtime-id}__{model-id}__{preset}.yaml` (double underscore between the parts; drop the `model-id` part for runtimes with empty `accepts_formats`). The optional top-level `id:` in YAML must match the filename stem; `llm config validate` checks that.

## CLI discovery

- **`llm list`** — scans `runtimes/*/manifest.yaml`, `$LLM_MODELS/registry.json`, `configs/*.yaml`, `benchmarks/*/bench.yaml`.
- **`llm config validate`** — for each config: runtime exists with the three scripts, `accepts_formats` rule for `model:` holds (required ⇔ non-empty), referenced model is in the registry and its `format` is compatible, `serve.host`/`serve.port` present, and settings resolve. Optional `readiness` must be a mapping if present.

## Git: what to commit

- Commit manifests, configs, scripts, benchmark metadata, and (per design) small benchmark results under `results/` once the benchmark workflow is wired.
- Do **not** commit machine-local settings, generated env files, or runtime state under `state/` (`running.json`, `history.jsonl`, `state/logs/*`) — that directory is for process-local data only. See `docs/lifecycle.md`.

## Stub packages

`stub-runtime`, `stub-bench`, and `configs/stub-runtime__default.yaml` are minimal smoke examples; replace them with real entries or add siblings alongside them. (There is intentionally no `stub-model` — models live in the per-machine registry now, not the repo.)
