# HOWTO: add a model

A **model** is a folder under `models/{model-id}/` that describes a weight set and implements how to materialize it under the WSL data root.

## 1. Create the folder

```text
models/my-model/
  README.md
  manifest.yaml
  pull.sh
```

## 2. Write `manifest.yaml`

Minimum fields:

```yaml
id: my-model
display_name: My quantized weights
description: >
  Source (HF repo, URL, …), quant, size, context — whatever you need to remember.
```

Add `source`, checksums, and other metadata as you harden reproducibility (see design spec §6.2).

## 3. Implement `pull.sh`

- Must populate **`$LLM_MODELS/{model-id}/`** (or subpaths you document), where `LLM_MODELS` comes from resolved settings.
- Should be **idempotent** (safe to re-run).
- Use `set -euo pipefail` and verify downloads when you have checksums in the manifest.

The CLI injects `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, and `LLM_CACHE` into bash every time it spawns one. For ad-hoc shell use, run:

```bash
eval "$(llm settings env)"
bash models/my-model/pull.sh
```

## 4. Verify

```bash
llm list models
llm config validate
```

## 5. Pull weights

```bash
llm setup           # once per machine, if not already done
llm model pull my-model
```

This runs `models/my-model/pull.sh` in WSL from the repo root with `LLM_*` env injected.

> **Note:** Model parameter schemas are a follow-up spec — for now, `pull.sh` keeps its free-form env contract from settings/`LLM_*`, unlike runtimes where `serve.params` is typed against `manifest.yaml`.

## See also

- [`repo-conventions.md`](repo-conventions.md)
- [Design spec §6.2](superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
