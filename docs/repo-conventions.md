# Repository conventions

This document matches the **current** repo layout and CLI behavior through lifecycle commands (`serve`, `stop`, …).

## Two roots (Hermes-style)

| Root | Default | Role |
|------|---------|------|
| **Data home** | `~/.loco` (`LOCO_HOME`) | `config.yaml`, `configs/`, models, builds, cache, `state/` |
| **Install** | `~/.loco/install` (`LOCO_INSTALL`) | Git clone: CLI, `runtimes/` recipes, `benchmarks/` |

End users edit launch configs only under **data home** `configs/`. Repo `configs/` are examples; `install.sh` copies them once at install.

## Root files (in git / install)

| File | Role |
|---|---|
| `requirements.yaml` | External prerequisites for `loco doctor` |
| `requirements.md` | Regenerated via `loco doctor render-requirements` |
| `specs.md` | Host/GPU/WSL snapshot via `loco specs` |

## Settings vs configs

Two namespaces, intentionally separate:

- **`loco settings ...`** edits `{data_home}/config.yaml` (where data lives on this machine).
- **`loco config show/validate`** operates on `{data_home}/configs/*.yaml` (launch units).

For manual bash, `eval "$(loco settings env)"` injects `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE`.

## Directory layout

| Path (install) | Contains |
|---|---|
| `runtimes/{id}/` | `manifest.yaml`, `build.sh`, `serve.sh`, `healthcheck.sh`, `README.md` |
| `configs/{config-id}.yaml` | Example launch units (seeded to data home) |
| `benchmarks/{id}/` | `bench.yaml`, `run.sh`, `README.md` |
| `src/llm_cli/` | Python Typer CLI |

| Path (data home) | Contains |
|---|---|
| `configs/{config-id}.yaml` | Your launch units |
| `runtimes/{id}/` | Per-install build state (`.installed`, venvs, …) |
| `models/` | Weights + `registry.json` |
| `state/` | `running.json`, `history.jsonl`, logs — see `docs/lifecycle.md` |
| `user/runtimes/` | Custom runtime recipes overriding install recipes |

Heavy artifacts are **not** in git.

## Naming

- **Runtime IDs** — lowercase and hyphens (e.g. `vllm-cuda`).
- **Model IDs** — lowercase and hyphens from HF repo + quant tag.
- **Config files** — `{runtime-id}__{model-id}__{preset}.yaml` under **data home** `configs/`.

## CLI discovery

- **`loco list`** — install recipes + user runtimes; configs from **data home only**; models from registry; benchmarks merged.
- **`loco config validate`** — configs in data home `configs/`.

## Git: what to commit

- Commit manifests, example configs, scripts, benchmark metadata in the **repo**.
- Do **not** commit machine `config.yaml`, data home trees, or `state/`.

## Stub packages

`stub-runtime`, `stub-bench`, and example configs are smoke examples; replace with real entries in your data home after install.
