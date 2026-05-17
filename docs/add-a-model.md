# HOWTO: add a model

Models live in a per-machine registry at `$LLM_MODELS/registry.json` (not in git). You don't write any YAML or scripts by hand; the CLI manages everything.

## Pull from Hugging Face (one shot)

For a single GGUF quant (URL points at the file):

```bash
llm model pull \
  https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf
```

For a whole safetensors-style repo:

```bash
llm model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
```

If the repo is ambiguous (mixed formats, multiple GGUF quants) `pull` will refuse and tell you to add `--format` and/or `--include`:

```bash
llm model pull https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF \
  --include "*UD-Q4_K_XL*"
```

Re-pulling an existing id refreshes the on-disk artifact and bumps `installed_at`:

```bash
llm model pull qwen-qwen2.5-7b-instruct
```

## Register local weights

```bash
llm model add my-finetune /home/me/llm/staging/my-finetune --format safetensors-dir
llm model add q4-local   /home/me/llm/staging/q4.gguf      --format gguf
```

Files are symlinked into `$LLM_MODELS/<id>/` (copied as a fallback if the FS rejects symlinks). The originals are untouched.

## Reference models in configs

Configs reference a model by id and use the `${model_path}` template inside `serve.params`:

```yaml
runtime: llamacpp
model: unsloth-qwen3.6-235b-a22b__ud-q4-k-xl
serve:
  host: 127.0.0.1
  port: 8080
  params:
    gguf_path: "${model_path}"
    n_gpu_layers: -1
    ctx: 8192
```

`llm config validate` enforces:
- `model:` is **required** when the runtime declares `accepts_formats: [...]` (non-empty).
- `model:` must be **absent** when the runtime declares `accepts_formats: []`.
- The model's `format` must be in the runtime's `accepts_formats`.
- The id must resolve to an entry in `$LLM_MODELS/registry.json`.

## Verify and uninstall

```bash
llm model list
llm model info <id>
llm model uninstall <id> [--purge]
```

`--purge` removes the symlinked / downloaded files under `$LLM_MODELS/<id>/` in addition to the registry row.

## Source kinds

Every registry entry has one of two `source` kinds:
- `hf` — pulled from Hugging Face; `pull <id>` will refresh it.
- `local` — registered with `llm model add`; `pull <id>` will refuse it.

## See also

- [`runtime-lifecycle.md`](runtime-lifecycle.md)
- [Models registry redesign spec](superpowers/specs/2026-05-17-models-registry-redesign.md)
