# HOWTO: add a runtime

A **runtime** is a folder under `runtimes/{runtime-id}/` that knows how to build and serve one inference stack (vLLM, llama.cpp, etc.). The control plane only shells into your scripts via WSL bash.

## 1. Create the folder

```text
runtimes/my-runtime/
  README.md
  manifest.yaml
  build.sh
  serve.sh
  healthcheck.sh
```

Use a stable `runtime-id` (directory name) — it appears in configs and CLI output.

## 2. Write `manifest.yaml`

Minimum useful fields:

```yaml
id: my-runtime                     # optional if same as directory name
display_name: My runtime (CUDA)
description: >
  One-line summary for `llm list` and docs.
```

You can add `upstream`, `arg_schema`, and other fields as in the design spec; they are not validated by the CLI yet.

## 3. Implement the three scripts

All are invoked from the **repo root** in WSL. The CLI injects `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, and `LLM_CACHE` into bash every time it spawns one. For ad-hoc shell use, run:

```bash
eval "$(llm settings env)"
bash runtimes/my-runtime/build.sh
```

| Script | Purpose (today) |
|---|---|
| `build.sh` | Idempotent build/install into `$LLM_DATA_ROOT/runtimes/{id}/` (or your layout) |
| `serve.sh` | Intended to start the server in the foreground for a given config (full contract in design doc) |
| `healthcheck.sh` | Exits 0 when the OpenAI-compatible endpoint is ready |

**Tip:** Keep scripts `set -euo pipefail` and fail loudly when env vars are missing.

## 4. Verify

```bash
llm list runtimes
llm config validate    # after you have a config pointing at this runtime
```

## 5. Build artifacts

```bash
llm setup           # once per machine, if not already done
llm build my-runtime
```

This runs `runtimes/my-runtime/build.sh` under WSL with the repo as cwd and `LLM_*` env injected.

## See also

- [`repo-conventions.md`](repo-conventions.md)
- [Design spec §6.1](superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
