# HOWTO: add a config

A **config** is a single file `configs/{config-id}.yaml` that names one runtime + one model and describes how to serve them together.

As of **0.2**, use **`llm config setup`** for an interactive wizard (VRAM-aware hints from the same logic as **`llm advisor`**) or **`llm config new`** for non-interactive scaffolding (`--runtime`, optional **`--model`**, **`--param k=v`**).

## 1. Naming

Prefer:

```text
{runtime-id}__{model-id}__{preset}.yaml
```

Example: `vllm-cuda__qwen2-7b-fp16__default.yaml`

The optional `id:` field inside the file should match the filename stem (without `.yaml`). `llm config validate` errors if they disagree.

## 2. Minimal YAML

Runtime-specific knobs belong under **`serve.params`** and must match the manifest **`serve:`** schema for that runtime.

```yaml
id: my-runtime__my-model__default
runtime: my-runtime
model: my-model
description: Optional human note

serve:
  host: 127.0.0.1
  port: 8000
  params:
    # keys depend on the runtime manifest (example for llamacpp-style stacks):
    gguf_path: "${model_path}"
    n_gpu_layers: -1
    ctx: 2048
    extra_args: ""

readiness:
  timeout_seconds: 180
```

## 3. `${data_root}` in `serve.env`

`llm config show` expands `${data_root}` to the resolved **`data_root`** from `paths.yaml` so you can see the values WSL scripts will use after sourcing `.llm-env`.

## 4. Validate

```bash
llm config validate
```

This checks that the runtime and model exist, required scripts are present, `serve.host` / `serve.port` exist, and `paths.yaml` loads.

## 5. Inspect

```bash
llm config show my-runtime__my-model__default
```

## See also

- [`wizards.md`](wizards.md), [`add-a-recommendation.md`](add-a-recommendation.md)
- [`add-a-runtime.md`](add-a-runtime.md), [`add-a-model.md`](add-a-model.md)
- [Design spec §6.3](superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
