# HOWTO: add a config

A **config** is a single file `configs/{config-id}.yaml` that names one runtime + one model and describes how to serve them together.

As of **0.2**, use **`llm config setup`** for an interactive wizard (VRAM-aware hints from the same logic as **`llm advisor`**) or **`llm config new`** for non-interactive scaffolding (`--runtime`, optional **`--model`**, **`--param k=v`**).

After you choose runtime and model, **`llm config setup`** edits **serve params** in the shared **param grid** (same component as interactive runtime **build** params and wizard **`review()`** — not separate per-field prompts). Optional params start **disabled**; **Space** enables the focused row. On save, **`serve.params`** contains **only enabled keys** (plus locked required / bound fields). On a TTY that grid supports **Ctrl+S** save, **Ctrl+X** abort, **Ctrl+A** toggle advanced tier, **Ctrl+← / Ctrl+→** paging, and **arrow keys** to move focus; plain/CI mode uses **`S` / `X` / `A`** instead. Color meanings (disabled vs enabled-empty vs enabled-set vs locked, focus, advanced accents, hints/errors) are defined in **`src/llm_cli/core/param_grid_theme.py`**. See **[`wizards.md`](wizards.md)** for the full shortcut list and behavior.

**Breaking change:** configs that listed every runtime catalog key under `serve.params` should be **recreated** with **`llm config setup`** (or trimmed by hand). The wizard does not strip stale keys you never disable in the grid — remove unwanted keys from YAML explicitly.

## 1. Naming

Prefer:

```text
{runtime-id}__{model-id}__{preset}.yaml
```

Example: `vllm-cuda__qwen2-7b-fp16__default.yaml`

The optional `id:` field inside the file should match the filename stem (without `.yaml`). `llm config validate` errors if they disagree.

## 2. Minimal YAML

Runtime-specific knobs belong under **`serve.params`**. Keys must exist in that runtime’s serve schema (**official** packages define it in **`runtimes/<id>/params.yaml`**). Only include params you **opted in** to — omitted keys are not passed to `serve.sh`. Catalog entries have **no `default:` field**; use **`llm advisor`** in the grid for suggestions.

```yaml
id: my-runtime__my-model__default
runtime: my-runtime
model: my-model
description: Optional human note

serve:
  host: 127.0.0.1
  port: 8000
  params:
    # required + any optional knobs you enabled in config setup:
    gguf_path: "${model_path}"
    ctx: 2048

readiness:
  timeout_seconds: 180
```

## 3. `${model_path}` and `bind: model_path`

Values may be the literal **`"${model_path}"`**. At serve/display time the CLI expands that to the registered model’s on-disk path when **`model:`** is set; validation fails if the token appears without **`model:`** or for an unknown id.

When the runtime’s **`params.yaml`** marks a serve key with **`bind: model_path`**, **`llm config new`** (with **`--model`**) and **`llm config setup`** pre-fill that key with **`"${model_path}"`** (locked, always saved); in **`config setup`** those cells are **read-only** and hidden from the parameter list.

## 4. `${data_root}` in `serve.env`

`llm config show` expands `${data_root}` to the resolved **`data_root`** from `paths.yaml` so you can see the values WSL scripts will use after sourcing `.llm-env`.

## 5. Validate

```bash
llm config validate
```

This checks that the runtime and model exist, required scripts are present, `serve.host` / `serve.port` exist, and `paths.yaml` loads.

## 6. Inspect

```bash
llm config show my-runtime__my-model__default
```

## See also

- [`wizards.md`](wizards.md), [`add-a-recommendation.md`](add-a-recommendation.md)
- [`add-a-runtime.md`](add-a-runtime.md), [`add-a-model.md`](add-a-model.md)
- [Design spec §6.3](superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
