# HOWTO: add a runtime

A **runtime** is a folder under `runtimes/{runtime-id}/` that describes how to **build**, **verify**, and **serve** one inference stack (llama.cpp, vLLM, …). The CLI orchestrates your scripts from WSL bash and validates configs against the typed schemas in `manifest.yaml`.

## 1. Folder layout

```text
runtimes/my-runtime/
  README.md          # human-facing notes (recommended)
  manifest.yaml      # id, requires, build/serve param schemas
  build.sh           # idempotent build under the data root
  verify.sh          # quick post-install sanity check (exit 0 = pass)
  serve.sh           # foreground server process
  healthcheck.sh     # readiness probe for `llm serve`
```

Use a stable `runtime-id` (directory name). It appears in configs, install paths, and `llm runtime …` output.

## 2. `manifest.yaml`

Top-level fields:

| Field | Meaning |
|---|---|
| `id` | Runtime id (defaults to directory name if omitted). |
| `display_name`, `description` | Shown in `llm runtime list` / `llm list`. |
| `official` | Optional marker for curated packages in this repo. |
| `requires` | External tools with `verify:` hooks for `llm doctor --runtime <id>`. |
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
    install_hint: "apt install cmake"
  - id: nvcc
    when: { build.flavor: cuda }
    verify:
      cmd: nvcc --version
      version_regex: 'release ([\d.]+)'
      min: "12.0"
    install_hint: "Install CUDA toolkit; see NVIDIA docs."

build:
  flavor:
    type: enum
    values: [cuda, cpu, vulkan]
    default: cuda
    prompt: "Which backend to build?"
  jobs:
    type: int
    default: 0
    prompt: "Parallel build jobs (0 = nproc)"

serve:
  gguf_path:
    type: path
    required: true
    env: LLM_LLAMACPP_GGUF
  n_gpu_layers:
    type: int
    default: -1
    env: LLM_LLAMACPP_N_GPU_LAYERS
  ctx:
    type: int
    default: 8192
    env: LLM_LLAMACPP_CTX
  extra_args:
    type: string
    default: ""
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

- **`required`** — must be set in config (`serve`) or supplied at install (`build`).
- **`default`** — used when omitted.
- **`prompt`** — interactive prompt during `llm runtime install` when not passed as `--param key=value`.
- **`env`** — explicit environment variable name for **serve** params mapped into `serve.sh` / `healthcheck.sh`. If omitted, the CLI derives **`LLM_<RUNTIME_ID>_<PARAM>`** (uppercase; hyphens → underscores).

Build-time values use **`LLM_BUILD_<PARAM>`** with the same normalization; the runtime id is omitted so every `build.sh` sees a uniform contract.

### `when:` on requirements

Each entry in `requires` may include `when:` so a dependency applies only for certain **build** parameter values, for example CUDA toolkit checks only when `build.flavor` is `cuda`. The CLI evaluates these clauses against the resolved build params during `llm doctor --runtime <id>`.

## 4. Script contracts

All scripts run from the **repo root** in WSL. Every invocation receives the standard settings env (`LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE`, …). For ad-hoc use:

```bash
eval "$(llm settings env)"
bash runtimes/my-runtime/build.sh
```

| Script | Role |
|---|---|
| **`build.sh`** | Idempotent clone/build/install under `$LLM_RUNTIMES/<runtime-id>/` (or your documented layout). Receives **`LLM_BUILD_*`** for each build param (see [`runtimes/llamacpp/build.sh`](../runtimes/llamacpp/build.sh)). |
| **`verify.sh`** | Optional but recommended. Exit **0** after install when the tree looks sane; non-zero fails `install`. |
| **`serve.sh`** | Start the server in the **foreground**. Handle **SIGTERM** for clean shutdown (`llm stop`). Receives **`LLM_SERVE_HOST`**, **`LLM_SERVE_PORT`**, plus env vars from **`serve`** params (`env:` or derived names). |
| **`healthcheck.sh`** | Exit **0** when ready for traffic; polled about once per second until timeout. Same env contract as `serve.sh`. |

## 5. Install flow and configs

1. **`llm runtime install <runtime-id>`** — prompts for build params (unless `--yes` / `--param`), runs `build.sh`, runs `verify.sh` if present, writes **`$LLM_RUNTIMES/<id>/.installed`** (JSON record with params, script hashes, schema hash).
2. **`llm runtime info <id>`** — shows manifest path, install state, drift hints.
3. Launch configs use **`serve.params`** (not free-form `serve.env`): keys must match the manifest `serve:` schema; values are validated and converted to env for serve/switch.

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

Example llamacpp-oriented snippet:

```yaml
serve:
  host: 127.0.0.1
  port: 8080
  params:
    gguf_path: "${data_root}/models/my-model/weights.gguf"
    n_gpu_layers: -1
    ctx: 8192
    extra_args: ""
```

## 6. Verification commands

```bash
llm runtime list
llm runtime info llamacpp
llm doctor --runtime llamacpp
llm config validate
llm serve stub-runtime__stub-model__default
```

**Serve gate:** if **`$LLM_RUNTIMES/<runtime-id>/.installed`** is missing, `llm serve` / `llm switch` refuse and suggest `llm runtime install <id>`.

## See also

- Spec: [`superpowers/specs/2026-05-17-runtime-manifest-and-installs.md`](superpowers/specs/2026-05-17-runtime-manifest-and-installs.md)
- Install lifecycle: [`runtime-lifecycle.md`](runtime-lifecycle.md)
- Repo layout: [`repo-conventions.md`](repo-conventions.md)
