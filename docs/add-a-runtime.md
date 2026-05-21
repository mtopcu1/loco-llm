# HOWTO: add a runtime

A **runtime** is a folder under `runtimes/{runtime-id}/` that describes how to **build** (official only), **verify**, and **serve** one inference stack. As of **0.2**, serve-time knobs live in **`params.yaml`**; `manifest.yaml` carries `kind: official | custom`, `accepts_formats`, and optional `requires`. Use **`loco runtime setup`** for a preset install or to scaffold a **`kind: custom`** runtime (no build scripts). The CLI orchestrates scripts from WSL bash and validates configs against those schemas.

## 1. Folder layout

```text
runtimes/my-runtime/
  README.md          # human-facing notes (recommended)
  manifest.yaml      # id, requires, build/serve param schemas
  build.sh           # idempotent build under the data root
  verify.sh          # quick post-install sanity check (exit 0 = pass)
  serve.sh           # foreground server process
  healthcheck.sh     # readiness probe for `loco serve`
```

Use a stable `runtime-id` (directory name). It appears in configs, install paths, and `loco runtime …` output.

## 2. `manifest.yaml`

Top-level fields:

| Field | Meaning |
|---|---|
| `id` | Runtime id (defaults to directory name if omitted). |
| `display_name`, `description` | Shown in `loco runtime list` / `loco list`. |
| `official` | Optional marker for curated packages in this repo. |
| `requires` | External tools with `verify:` hooks for `loco doctor --runtime <id>`. |
| `build` | Mapping of **build-time** parameters (schema → env during `install`/`rebuild`). |
| `serve` | Mapping of **serve-time** parameters (must align with `serve.params` in configs). |

### Full example: `llamacpp` (this repo)

See [`runtimes/llamacpp/manifest.yaml`](../runtimes/llamacpp/manifest.yaml):

```yaml
id: llamacpp
display_name: llama.cpp (llama-server)
official: true
description: >
  Builds upstream llama.cpp and serves GGUF weights via the OpenAI-compatible
  HTTP API (`llama-server`).

requires:
  - id: cmake
    verify:
      cmd: cmake --version
      version_regex: 'cmake version ([\d.]+)'
      min: "3.16"
    install_hint: |
      pip install -U "cmake>=3.16"
      Debian/Ubuntu: sudo apt install cmake
      https://cmake.org/download/
  - id: nvcc
    when: { build.flavor: cuda }
    verify:
      cmd: nvcc --version
      version_regex: 'release ([\d.]+)'
      min: "12.0"
    install_hint: |
      NVIDIA CUDA Toolkit (nvcc) — install a version matching your driver.
      https://developer.nvidia.com/cuda-downloads

build:
  flavor:
    type: enum
    values: [cuda, cpu, vulkan]
    tier: common
    prompt: "Which backend to build?"
  jobs:
    type: int
    tier: common
    prompt: "Parallel build jobs (0 = nproc)"

serve:
  gguf_path:
    type: path
    required: true
    env: LLM_LLAMACPP_GGUF
  n_gpu_layers:
    type: int
    env: LLM_LLAMACPP_N_GPU_LAYERS
  ctx:
    type: int
    env: LLM_LLAMACPP_CTX
  extra_args:
    type: string
    env: LLM_LLAMACPP_EXTRA_ARGS
```

Minimal smoke runtime (empty schemas):

```yaml
id: stub-runtime
display_name: Stub Runtime (smoke)
official: true
description: >
  Minimal runtime package for exercising discovery and install flow.
build: {}
serve: {}
```

## 3. Param types and `env:`

Each key under `build:` / `serve:` is a parameter spec:

| `type` | Accepts |
|---|---|
| `string` | Plain string |
| `int` | Integer (string forms parsed) |
| `float` | Floating point |
| `bool` | Boolean-ish strings |
| `enum` | One of `values:` |
| `path` | Path string; configs may use `${data_root}/…`; expanded when building serve env |

Optional fields:

- **`required`** — must be enabled in the param grid and present in `serve.params` / `build_params` (locked rows always count).
- **`prompt`** — label in the param grid during `loco runtime install` / config setup.
- **`tier`** — `common` (default) or `advanced`; advanced rows need **Ctrl+A** in the grid.
- **`description`** — shown in the grid list/detail; use for operator-facing notes.
- **`env`** — explicit environment variable name for **serve** params mapped into `serve.sh` / `healthcheck.sh`. If omitted, the CLI derives **`LLM_<RUNTIME_ID>_<PARAM>`** (uppercase; hyphens → underscores).
- **`bind`** — optional; **`model_path`** ties this key to the selected registry model. Wizards and `loco config new` write **`"${model_path}"`** for that param when `model:` is set (see [`add-a-config.md`](add-a-config.md)).

Do **not** use **`default:`** in `params.yaml` or inline manifest schemas — the loader rejects it. Suggested values come from **`loco advisor`** in the param grid detail view, not from the catalog.

### Opt-in parameters (build and serve)

Optional knobs are **opt-in** everywhere the param grid is used (`loco config setup`, `loco runtime install`, wizard **`review()`**):

| Behavior | Detail |
|---|---|
| Grid | Optional rows start **disabled** (`[ ]`). **Space** enables a row; disabled rows are cleared. Required / bound rows are **locked** (`[•]`) and always saved. |
| Saved maps | **`serve.params`** in configs and **`build_params`** in `.installed` list **only keys you enabled** (plus locked required keys). Omitted keys are not written and are not exported to `serve.sh` / `build.sh`. |
| `--yes` / `--param` | `loco runtime install --yes` skips the grid; only explicit **`--param key=value`** flags are stored (may be `{}` when nothing is required). |
| Suggestions | **`loco advisor`** supplies hints in grid detail; scripts apply their own fallbacks for env vars that were not set. |

**Breaking change:** configs that previously listed every catalog key under `serve.params` should be **recreated** with **`loco config setup`** (or hand-edited to a sparse map). Keys you no longer want must be removed from YAML — they are not silently dropped on save.

Build-time values use **`LLM_BUILD_<PARAM>`** with the same normalization; the runtime id is omitted so every `build.sh` sees a uniform contract.

### Official serve catalogs (llamacpp, vLLM)

Official **`kind: official`** packages here store **serve** params in **`runtimes/<id>/params.yaml`** (tiered **`common`** / **`advanced`**), not only the small inline stubs in older examples. **`llamacpp`** lists an exhaustive **`llama-server`** flag catalog (tracked to a pinned upstream git ref in **`build.git_ref`**). **`vllm`** lists the knobs surfaced for **`vloco serve`**, including a **`model`** entry with **`bind: model_path`**. See [`runtimes/llamacpp/params.yaml`](../runtimes/llamacpp/params.yaml) and [`runtimes/vllm/params.yaml`](../runtimes/vllm/params.yaml).

### `when:` on requirements

Each entry in `requires` may include `when:` so a dependency applies only for certain **build** parameter values, for example CUDA toolkit checks only when `build.flavor` is `cuda`. The CLI evaluates these clauses against the resolved build params during `loco doctor --runtime <id>`.

## 4. Script contracts

All scripts run from the **repo root** in WSL. Every invocation receives the standard settings env (`LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE`, …). For ad-hoc use:

```bash
eval "$(loco settings env)"
bash runtimes/my-runtime/build.sh
```

| Script | Role |
|---|---|
| **`build.sh`** | Idempotent clone/build/install under `$LLM_RUNTIMES/<runtime-id>/` (or your documented layout). Receives **`LLM_BUILD_*`** for each build param (see [`runtimes/llamacpp/build.sh`](../runtimes/llamacpp/build.sh)). |
| **`verify.sh`** | Optional but recommended. Exit **0** after install when the tree looks sane; non-zero fails `install`. |
| **`serve.sh`** | Start the server in the **foreground**. Handle **SIGTERM** for clean shutdown (`loco stop`). Receives **`LLM_SERVE_HOST`**, **`LLM_SERVE_PORT`**, plus env vars from **`serve`** params (`env:` or derived names). |
| **`healthcheck.sh`** | Exit **0** when ready for traffic; polled about once per second until timeout. Same env contract as `serve.sh`. |

## 5. Install flow and configs

1. **`loco runtime install <runtime-id>`** — param grid for build params (unless `--yes` / `--param` only), runs `build.sh`, runs `verify.sh` if present, writes **`$LLM_RUNTIMES/<id>/.installed`** (JSON record with **opted-in** `build_params`, script hashes, schema hash).
2. **`loco runtime info <id>`** — shows manifest path, install state, drift hints.
3. Launch configs use **`serve.params`** (not free-form `serve.env`): keys must match the runtime serve schema; only **enabled** keys are stored; values are validated and converted to env for serve/switch.

Example stub config:

```yaml
id: stub-runtime__stub-model__default
runtime: stub-runtime
model: stub-model
serve:
  host: 127.0.0.1
  port: 18080
  params: {}
```

Example llamacpp-oriented snippet (sparse — only knobs you enabled in **`loco config setup`**):

```yaml
serve:
  host: 127.0.0.1
  port: 8080
  params:
    gguf_path: "${model_path}"
    n_gpu_layers: -1
    ctx: 8192
```

## Metrics (optional)

Runtimes may expose a Prometheus text endpoint for the dashboard live-metrics pipeline. The block is **optional**; omit it or set `metrics: null` when the server has no `/metrics` scrape target.

```yaml
metrics:
  endpoint: /metrics          # path on the serve host:port
  format: prometheus          # only prometheus in v1
  fields:
    tps_decode:
      promql_metric: myruntime:tokens_per_second{phase="decode"}
      label: "Decode TPS"     # UI label
      unit: "tok/s"
      multiplier: 1           # optional scale (e.g. 1000 for seconds→ms)
```

- **`promql_metric`** — metric name, optionally with `{label="value"}` selectors. The dashboard parser matches exported Prometheus samples by name and labels (not full PromQL).
- **Finding names** — run the server, `curl http://127.0.0.1:<port>/metrics`, and grep for counters/gauges you care about (throughput, TTFT, queue depth).
- **llama.cpp** — enable with serve param `metrics: true` (`--metrics`); metric names vary by build; adjust the manifest to match your `llama-server` output.
- **Stub / custom runtimes** — use `metrics: null` so the UI shows the “no live metrics” state.

## 6. Verification commands

```bash
loco runtime list
loco runtime info llamacpp
loco doctor --runtime llamacpp
loco config validate
loco serve stub-runtime__stub-model__default
```

**Serve gate:** if **`$LLM_RUNTIMES/<runtime-id>/.installed`** is missing, `loco serve` / `loco switch` refuse and suggest `loco runtime install <id>`.

## See also

- Spec: [`superpowers/specs/2026-05-17-runtime-manifest-and-installs.md`](superpowers/specs/2026-05-17-runtime-manifest-and-installs.md)
- Install lifecycle: [`runtime-lifecycle.md`](runtime-lifecycle.md)
- Repo layout: [`repo-conventions.md`](repo-conventions.md)
