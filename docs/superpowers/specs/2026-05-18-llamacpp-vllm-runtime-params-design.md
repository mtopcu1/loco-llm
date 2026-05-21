# llamacpp & vloco runtime params — design spec

_Date: 2026-05-18_  
_Status: Approved by user — ready for implementation planning_

## 1. Purpose

Expand the shipped **llamacpp** runtime from a barebones build/serve schema to an **exhaustive, typed catalog** of upstream knobs, using the existing **`tier: common | advanced`** gate so wizards stay approachable. Add a first official **vllm** runtime (pip/venv install, no containers in this release). Fix config setup so **model-bound path params** are never prompted when a model is already selected.

Builds on the 0.2 schema split (`manifest.yaml` build block + sibling `params.yaml` serve block) and wizard/advisor work in [`2026-05-18-wizards-and-advisor.md`](2026-05-18-wizards-and-advisor.md).

## 2. Goals

- **llamacpp serve:** Every `llama-server` flag we support is declared in `params.yaml` with type, default, tier, description, and env mapping.
- **llamacpp build:** Major cmake/clone knobs declared in `manifest.yaml` `build:` with the same tier pattern.
- **vllm:** New `runtimes/vllm/` official runtime — venv + `pip install vllm`, exhaustive tiered serve params, `accepts_formats: [safetensors-dir]`.
- **Config UX:** Params with `bind: model_path` auto-fill as `${model_path}` when `model:` is set; wizards skip prompting for them.
- **Backward compatibility:** Existing configs with four llamacpp keys remain valid; new keys are optional with schema defaults.

## 3. Non-goals

- Docker/container runtimes (future).
- Generic recommendation framework beyond existing `core/recommendations.py` llamacpp branch (`ctx`, `n_gpu_layers` only for this release).
- Auto-generating `params.yaml` from `--help` (hand-curated catalog; optional CI drift check is a follow-up).
- Changing config top-level shape (`serve.host`, `serve.port`, `serve.params`, `model:`).

## 4. Maintenance strategy

**Primary (v1):** Hand-curated catalogs in-repo. Each param gets human-written `description` and tier assignment.

**Follow-up (recommended):** CI or unit test that diffs declared param keys against `llama-server --help` / `vloco serve --help` and warns on missing or removed flags (non-blocking initially).

## 5. Tier assignment rules

| Tier | When to use |
|---|---|
| **common** | Knobs users tune per model/GPU/session; safe defaults; install/config wizard shows without “reveal advanced”. |
| **advanced** | Rare flags, expert tuning, build options that can break compiles or add long install time, speculative decoding, cache-type minutiae, etc. |

**Build tier rule:** If a param can add significant compile time or break on wrong hardware → **advanced**.

**Serve tier rule:** If a param is needed for >~80% of first configs (ctx, GPU layers, batch, threads) → **common**; long tail → **advanced**.

`walk_tier()` / `do_config_setup()` already reveal advanced only after confirm. Runtime **install** wizard should use the same pattern for **build** params (today install uses `typer.prompt` for all build keys — extend to tier-aware walk for interactive install).

## 6. Model-bound params (`bind: model_path`)

### Problem

`loco config setup` prompts for every serve param, including `gguf_path`, even after the user picks a model. Weights location is already defined by the registry entry.

### Solution

Extend `ParamSpec` with optional **`bind: model_path`**.

When a config has **`model:`** set:

1. **Skip** wizard prompt for bound params.
2. **Write** `serve.params.<key>: "${model_path}"` in YAML.
3. **Review screen** shows the binding (e.g. `gguf_path → ${model_path}`); user may still edit that row for a hardcoded override.
4. **`loco config new --runtime X --model Y`** auto-injects bound params unless `--param key=…` explicitly overrides.

At **serve** time, existing `expand_path_for_serve()` resolves `${model_path}` to:

`$LLM_MODELS/<model_id>/<artifact.primary>`

### Params marked `bind: model_path`

| Runtime | Param key | Notes |
|---|---|---|
| llamacpp | `gguf_path` | Primary GGUF file via registry `artifact.primary` |
| vllm | `model` | Maps to `vloco serve --model`; value `${model_path}` for local safetensors dirs |

When **no** `model:` (runtimes with empty `accepts_formats`), bound params behave like normal required path params (prompt if interactive).

### Schema example

```yaml
gguf_path:
  type: path
  required: true
  bind: model_path
  env: LLM_LLAMACPP_GGUF
  tier: common
  description: "GGUF weights; resolved from selected model when bound."
```

### Code touchpoints

- `src/llm_cli/core/params.py` — parse `bind` on `ParamSpec`
- `src/llm_cli/commands/config_cmd.py` — skip prompt + auto-inject in `do_config_setup` / `do_config_new`
- `tests/integration/test_cli_config_setup.py` — assert no gguf prompt when model selected

## 7. Phase 1 — llamacpp

### 7.1 Build params (`manifest.yaml`)

**Common (defaults match today’s happy path):**

| Key | Type | Default | Notes |
|---|---|---|---|
| `flavor` | enum | `cuda` | `cuda` \| `cpu` \| `vulkan` |
| `jobs` | int | `0` | `0` = nproc |
| `git_ref` | string | pinned release tag | Stop cloning floating `main` by default |

**Advanced (examples — finalize against pinned `git_ref` cmake options):**

| Key | Type | Notes |
|---|---|---|
| `cmake_build_type` | enum | `Release`, `RelWithDebInfo`, `Debug` |
| `cublas` | bool | When `flavor=cuda` |
| `flash_attn` | bool | Build-time flash attention |
| `native` | bool | `-march=native` |
| `cuda_architectures` | string | Explicit SM list when not native |
| `static` | bool | Prefer static linking |
| `clean_build` | bool | Remove `build/` before configure |
| _(others)_ | | Wire remaining upstream cmake toggles we commit to support |

**`build.sh`:** Map each `LLM_BUILD_*` env var to cmake `-D` flags. Undeclared options stay off.

**Interactive install:** Tier-aware prompts (common first, optional advanced reveal) instead of flat prompt list for every key.

### 7.2 Serve params (`params.yaml`)

Source: `llama-server --help` for the pinned `git_ref`.

**Common (~15–25 keys, illustrative):**

- `gguf_path` (`bind: model_path`)
- `n_gpu_layers`, `ctx`
- `batch_size`, `ubatch_size`
- `threads`, `threads_batch`
- `parallel`
- Runtime flash-attn / GPU split basics (`split_mode`, `tensor_split` if applicable)
- `rope_freq_base`, `rope_freq_scale`
- `extra_args` (string, advanced tier — escape hatch for flags not yet in catalog)

**Advanced:** All remaining supported `llama-server` flags (cache types, defrag, cont-batching, speculative decoding, embedding/rerank modes, mlock/mmap/numa, etc.).

**`serve.sh`:** Construct argv explicitly from `LLM_LLAMACPP_*` env vars; omit flags when value is empty/default; append `extra_args` last.

### 7.3 Config migration

- Existing configs keep working (subset of keys + `${model_path}` or literals).
- Replace `gguf_path: null` in tracked examples with `gguf_path: "${model_path}"` when `model:` is set.
- `loco config validate` — no change to contract; unknown keys still error, missing required keys error unless bound+model satisfies path.

### 7.4 Advisor

No expansion in this release — keep `ctx` and `n_gpu_layers` only.

### 7.5 Tests

- Unit: `parse_schema` accepts `bind`; bound params skipped in setup walk (mocked wizards).
- Unit: each `params.yaml` key referenced in `serve.sh` (static grep or manifest test).
- Integration: install/build mocked; config setup with model skips `gguf_path` prompt; written YAML contains `${model_path}`.
- Optional follow-up: help-text drift test.

## 8. Phase 2 — vllm official runtime

### 8.1 Identity

- **Runtime id:** `vllm` (not `vllm-cuda`).
- **`kind: official`**
- **`accepts_formats: [safetensors-dir]`**

### 8.2 Layout

```text
runtimes/vllm/
  manifest.yaml
  params.yaml
  build.sh
  verify.sh
  serve.sh
  healthcheck.sh
  README.md
```

### 8.3 Build (pip/venv)

**`build.sh`:**

```bash
python3 -m venv "$LLM_RUNTIMES/vllm/.venv"
"$LLM_RUNTIMES/vllm/.venv/bin/pip" install -U pip
# version + extras from LLM_BUILD_* env
pip install "vllm==${LLM_BUILD_VLLM_VERSION}"  # or unpinned default
```

**Common build params:**

| Key | Type | Default |
|---|---|---|
| `vllm_version` | string | Latest stable pin (explicit version in manifest default) |
| `pip_extra` | enum | `cuda` \| `cpu` \| `none` |

**Advanced build params:**

| Key | Type | Notes |
|---|---|---|
| `extra_pip_packages` | string | Comma-separated add-ons |
| `force_reinstall` | bool | `pip install --force-reinstall` |

**`requires:`** python (global), pip; CUDA driver check when `pip_extra=cuda`.

**`verify.sh`:** `"$LLM_RUNTIMES/vllm/.venv/bin/vllm" --version` exits 0.

### 8.4 Serve params

Source: `vloco serve --help`.

**Common (illustrative):**

- Model path param with `bind: model_path` (maps to vllm `--model`)
- `dtype`, `max_model_len`, `gpu_memory_utilization`
- `tensor_parallel_size`, `pipeline_parallel_size`
- `enforce_eager`, `swap_space`, `max_num_seqs`
- `extra_args`

**Advanced:** Quantization overrides, LoRA, speculative config, tokenizer/trust flags, worker settings, etc.

**`serve.sh`:** Invoke `"$LLM_RUNTIMES/vllm/.venv/bin/vllm" serve …` with env-mapped flags.

**`healthcheck.sh`:** HTTP GET `http://$LLM_SERVE_HOST:$LLM_SERVE_PORT/v1/models` (upgrade from TCP-only probe).

### 8.5 Example config

Add `configs/vllm__<model-id>__default.yaml` once a suitable safetensors registry entry exists (or document in README as manual step).

### 8.6 Tests

- Integration: mock `pip install`; runtime list shows `vllm`; install writes `.installed`.
- Config setup with safetensors model: bound model path auto-filled.
- `runtime install` / `rebuild` work; `kind: official` path.

## 9. Documentation updates

| Doc | Change |
|---|---|
| `docs/add-a-runtime.md` | Document `bind:`; expanded llamacpp example; vllm section |
| `docs/wizards.md` | Note model-bound params skipped in config setup |
| `docs/add-a-config.md` | `${model_path}` + bind behavior |
| `docs/add-a-recommendation.md` | Optional note: future vllm branch |

## 10. Implementation order

1. **`ParamSpec.bind`** + config setup/new auto-inject + tests.
2. **llamacpp** exhaustive catalogs + `build.sh` / `serve.sh` + tiered install prompts + config example fixes.
3. **Optional:** build-param tier walk in `runtime install` interactive path.
4. **vllm** runtime package + tests + one example config.
5. **Docs** + optional help drift check.

## 11. Success criteria

- [ ] `loco config setup` with llamacpp + registered model does **not** prompt for `gguf_path`; YAML contains `${model_path}`.
- [ ] `loco config new --runtime llamacpp --model <id>` injects bound params by default.
- [ ] llamacpp `params.yaml` covers full `llama-server` surface (common/advanced split documented in file header comment).
- [ ] llamacpp build schema covers agreed cmake knobs; default install behavior unchanged vs today for `--yes`.
- [ ] `loco runtime install vllm --yes` succeeds in WSL with pip; `loco serve` works with a safetensors config (manual smoke).
- [ ] Full pytest green.

## 12. References

- [`2026-05-18-wizards-and-advisor.md`](2026-05-18-wizards-and-advisor.md)
- [`2026-05-17-runtime-manifest-and-installs.md`](2026-05-17-runtime-manifest-and-installs.md)
- Current packages: `runtimes/llamacpp/`, `src/llm_cli/core/params.py`, `src/llm_cli/core/config_resolve.py`
