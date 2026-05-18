# LocalLLM Runtime Manifests & Installs

_Date: 2026-05-17_
_Status: Approved by user, ready for implementation planning_

> **Updated 2026-05-18:** the serve-time parameter schema lives in a sibling **`params.yaml`**, and manifests gain **`kind: official | custom`** — see [`2026-05-18-wizards-and-advisor.md`](2026-05-18-wizards-and-advisor.md).

## 1. Purpose

Make runtimes a first-class, schema-driven object in the CLI. Today, adding a runtime is "drop five files in a folder and hope the configs match." This spec turns each runtime into a typed manifest with a build-time and serve-time parameter schema, and adds a `llm runtime` command group that installs, verifies, lists, and uninstalls them. Configs become typed parameter sets validated against the chosen runtime's schema. The CLI is the only thing that translates params to env vars at script-spawn time, so a future web UI can render the same schema as a form with no extra work.

## 2. Problems solved

- **Authoring runtimes is hand-wavy.** Three untyped bash scripts plus a free-form `env:` dict in every config means typos and stale param names silently propagate.
- **There is no "ready to serve" gate.** `llm serve` happily spawns against a runtime whose `build.sh` was never run, then surfaces the failure mid-spawn.
- **`requirements.yaml` is global.** Adding a CUDA-only dep warns CPU-only users; uninstalled-runtime deps still appear in `llm doctor` output.
- **Setup wants to "help" too much.** Any attempt to bundle 10–30 minute builds into `llm setup` turns first-run into an hour-long block; failures inside setup are especially painful.
- **Configs aren't replicable.** A config can name any env var it wants; whether the runtime understands that var is anyone's guess until serve crashes.

## 3. Goals

- One typed `manifest.yaml` per runtime declares its build schema, serve schema, and external dependencies (with conditional `when:` clauses).
- One CLI verb to install a runtime: `llm runtime install <id>`, interactive by default, scriptable via `--param`/`--yes`.
- One detection mechanism for "installed": the `.installed` record file the CLI writes after `build.sh` succeeds and `verify.sh` (if present) passes.
- `llm serve <cfg>` hard-errors when the runtime is not installed, with a fix-it hint.
- Configs use typed `serve.params`, validated against the runtime's serve schema. Unknown keys and missing required keys are hard errors.
- `llm doctor` scopes external-dep checks to **currently installed** runtimes by default, with `--all` for completeness.
- `llm setup` never blocks on a build. It writes settings and prints a fixed onboarding hint.
- All four contract scripts (`build.sh`, `verify.sh`, `serve.sh`, `healthcheck.sh`) are uniform across "official" and "custom" runtimes. Provenance is a manifest field, not a folder split.

## 4. Non-goals

- **Model parameter schema.** Models keep today's `pull.sh` + free-form env contract for now. A follow-up spec will mirror the runtime schema design for models (quant selection, etc.).
- **Multi-flavor coexistence.** One install per runtime id at a time. Switching flavor = rebuild.
- **Remote runtime registry.** Runtimes are folders shipped in this repo (or user-added to it). No download mechanism, no catalog server.
- **Per-config build params.** Build flavor and other build-time choices live with the install, not the config.
- **Automatic schema migration.** If a manifest's `build:` schema changes after a runtime is installed, the install keeps its old `build_params`; `llm runtime info` shows the drift and the user runs `llm runtime rebuild <id> --reset` to re-prompt. No magic.
- **Hot reconfigure.** Edit a config → `llm switch <same-cfg>` restarts. No live param reload.
- **Parallel installs.** Sequential only; `for rt in a b; do llm runtime install $rt; done` is the answer.
- **Bulk install during `llm setup`.** Removed entirely; setup only handles settings + an onboarding hint.

## 5. Architecture

### 5.1 Runtime manifest

`runtimes/<id>/manifest.yaml` is the source of truth for what the runtime accepts and what it depends on. Example for `llamacpp`:

```yaml
id: llamacpp
display_name: llama.cpp (llama-server)
official: true
description: >
  Builds upstream llama.cpp and serves GGUF via /v1 (OpenAI-compatible).

requires:                            # per-runtime external deps
  - id: cmake
    verify: { cmd: cmake --version, version_regex: 'cmake version ([\d.]+)', min: "3.16" }
    install_hint: "apt install cmake"
  - id: nvcc
    when: { build.flavor: cuda }     # only required when CUDA flavor is chosen
    verify: { cmd: nvcc --version, version_regex: 'release ([\d.]+)', min: "12.0" }
    install_hint: "Install CUDA toolkit; see NVIDIA docs."

build:                               # params asked once, baked into the install
  flavor:
    type: enum
    values: [cuda, cpu, vulkan]
    default: cuda
    prompt: "Which backend to build?"
  jobs:
    type: int
    default: 0                       # 0 → nproc
    prompt: "Parallel build jobs (0 = nproc)"

serve:                               # params validated per-config; injected as env
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

#### 5.1.1 Param types (v1)

| Type | YAML scalar | Validation | Webui widget |
|---|---|---|---|
| `string` | string | as-is | text input |
| `int` | int | parse as int | number input |
| `float` | float | parse as float | number input |
| `bool` | bool | truthy/falsy | checkbox |
| `enum` | string | must be in `values:` | radio / select |
| `path` | string | expanded (see 5.1.3) | text input + browse |

Every param accepts: `default`, `required` (default `false`), `prompt` (defaults to the param key), `env` (defaults to `LLM_<RUNTIME_UPPER>_<PARAM_UPPER>`).

#### 5.1.2 `when:` clauses

A `requires:` entry may carry `when: { build.<param>: <value> }`. The CLI evaluates the clause against the resolved build params and skips the requirement if the clause does not match. v1 supports only `build.<param>: <scalar>` equality. (Future: serve-time `when:` clauses; logical ops.)

For `llm runtime install` and `llm doctor --runtime <id>`, the resolved build params come from CLI flags + interactive prompts (or, on a re-check of an installed runtime, from `.installed.build_params`). For `llm doctor --all` against an *uninstalled* runtime, the build schema's `default:` values are used as the resolved params; entries whose `when:` references a param with no default are listed as conditional (annotated, not failed).

#### 5.1.3 Path-template expansion

For `type: path` params, the CLI expands the following tokens before injecting the env var. No shell is involved.

| Token | Resolves to |
|---|---|
| `~` | `Path.home()` |
| `${data_root}` | `settings.data_root` |
| `${runtimes_dir}` | `settings.runtimes_dir` |
| `${models_dir}` | `settings.models_dir` |
| `${cache_dir}` | `settings.cache_dir` |

Unknown `${...}` tokens are an error (caught at `llm config validate`).

#### 5.1.4 Provenance

`official: true` is set on runtimes we ship. Absent or `false` is treated as user-added. The field affects only how `llm runtime list` groups output; install / serve / validate behavior is uniform.

### 5.2 Script contract

| Script | Required | Role |
|---|---|---|
| `build.sh` | yes | Reads `LLM_BUILD_<PARAM>` env vars (CLI sets them from the `build:` schema). Idempotent. |
| `verify.sh` | optional | "Binary works" probe with no model needed (e.g. `llama-server --version`). Exit 0 = OK. CLI runs it right after `build.sh` and on `llm doctor --runtime <id>`. |
| `serve.sh` | yes | Reads env vars per the `serve:` schema. Foreground. Handles SIGTERM cleanly. |
| `healthcheck.sh` | yes | Existing contract — exit 0 once the running server is ready. |

`build.sh` does not write the install marker; the CLI does, after `build.sh` exit 0 AND `verify.sh` exit 0 (or `verify.sh` absent).

### 5.3 Install record (`.installed`)

Path: `${runtimes_dir}/<id>/.installed`. JSON object; one record per runtime. Example:

```json
{
  "runtime_id": "llamacpp",
  "installed_at": "2026-05-17T17:45:00Z",
  "build_params": { "flavor": "cuda", "jobs": 0 },
  "build_sh_sha256": "5d41402abc4b2a76b9719d911017c592...",
  "verify_passed": true,
  "schema_hash": "8f14e45fceea167a5a36dedd4bea2543..."
}
```

| Field | Meaning |
|---|---|
| `runtime_id` | Matches the manifest `id`. Sanity check on read. |
| `installed_at` | ISO-8601 UTC. |
| `build_params` | The full resolved param map used for this install (defaults included). |
| `build_sh_sha256` | sha256 of the `build.sh` contents at install time. Informational only (drift shown by `llm runtime info`, no behavior change at serve time). |
| `verify_passed` | `true` if `verify.sh` ran and exited 0; `null` if `verify.sh` was absent. (A nonzero exit aborts the install entirely — `.installed` is not written, so the field is never `false`.) |
| `schema_hash` | sha256 of the canonicalized `build:` schema at install time. Drives the "schema changed since install" warning in `llm runtime info`. |

Detection: a runtime is "installed" iff `.installed` exists and parses. No subprocess on the hot path.

### 5.4 Config shape

`configs/<id>.yaml` becomes:

```yaml
id: llamacpp__unsloth-qwen3.6-35b-a3b__default
runtime: llamacpp
model: unsloth-qwen3.6-35b-a3b
description: >
  llama-server + Unsloth Qwen3.6-35B-A3B (UD-Q4_K_XL).

serve:
  host: 127.0.0.1
  port: 8080
  params:
    gguf_path: "${models_dir}/unsloth-qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"
    n_gpu_layers: -1
    ctx: 8192

readiness:
  timeout_seconds: 900
```

Validation rules (`llm config validate`):

| Condition | Result |
|---|---|
| Unknown key in `serve.params` | Hard error; suggest closest valid name. |
| Required param missing | Hard error. |
| Type mismatch | Hard error. |
| Enum value not in `values:` | Hard error; list valid values. |
| `path` template uses unknown token | Hard error. |
| Runtime referenced does not exist | Hard error (today's behavior). |
| Runtime referenced exists but is **not installed** | Warning (yellow), exit 0. Configs can be authored ahead of installs. |

Defaults from the schema are filled in **at env-build time**, not when reading the YAML, so the file stays minimal and the webui form pre-fills from the schema rather than from the YAML.

### 5.5 CLI surface

Today's top-level `llm build` and `llm pull` are removed. Two new groups:

```text
llm runtime list                 # id, official?, installed?, flavor, last built; --json
llm runtime info <id>            # manifest schema, install record, requirements status, drift
llm runtime install <id>         # interactive: prompts each `build:` param; --param k=v, --yes
llm runtime uninstall <id>       # removes .installed marker; --purge also rm -rf the install dir
llm runtime rebuild <id>         # reuses stored build_params unless --reset

llm model list                   # id, has weights?, source kind
llm model info <id>              # manifest + install state
llm model pull <id>              # runs pull.sh (unchanged for v1)
```

#### 5.5.1 `llm runtime install <id>` flow

1. Load manifest → typed schema.
2. Resolve build params:
   - From `--param k=v` flags (repeatable; one occurrence per param key, last wins on duplicates).
   - Interactive prompts (Rich) for any unset params, with default pre-filled.
   - `--yes` accepts all defaults non-interactively; errors if any required-no-default is missing.
3. Pre-flight dependencies: `llm doctor --runtime <id>` with the resolved build params (so `when:` clauses evaluate correctly). Refuse with install hints if anything is missing.
4. Build the env vars for `build.sh`: each build param resolves to its declared `env:` name (or the derived `LLM_BUILD_<PARAM_UPPER>` if no `env:` was declared). Invoke `runtimes/<id>/build.sh` via the existing WSL bash runner.
5. If `verify.sh` exists, run it with the same env. Exit non-zero from either step aborts; no `.installed` written.
6. Write `.installed` (5.3). Append `{action:"runtime-install", id, build_params}` to `state/history.jsonl`.
7. Print a one-line success: `installed llamacpp (flavor=cuda)`.

#### 5.5.2 `llm runtime uninstall <id>`

- Removes the `.installed` marker. Build artifacts under `${runtimes_dir}/<id>/` are left intact (a re-install reuses them; a half-broken build can be salvaged).
- `--purge` additionally `rm -rf ${runtimes_dir}/<id>/`. Confirmation prompt unless `--yes`.
- Appends `{action:"runtime-uninstall", id, purge}` to history.

#### 5.5.3 `llm runtime rebuild <id>`

- Reuses `build_params` from the existing `.installed` record.
- `--reset` discards them and re-prompts (or accepts `--param` overrides).
- Internally: uninstall (no purge) → install. History: one `runtime-rebuild` event.

#### 5.5.4 `llm runtime info <id>`

Renders: manifest schema (build + serve), `.installed` (if any), per-requirement status (✓/✗ with installed version), and the two drift indicators:

- `build.sh` sha vs `.installed.build_sh_sha256` (informational).
- `schema_hash` of current manifest vs `.installed.schema_hash` (warning if changed: "schema changed since install; rebuild to refresh").

### 5.6 `llm serve` gate

Before any spawn, `llm serve` checks `.installed` for the config's runtime. If absent:

```text
error: runtime 'llamacpp' is not installed
hint:  llm runtime install llamacpp
```

Exit 1. No history event written, no port probe attempted.

### 5.7 Setup flow

`llm setup` does not touch runtimes. After settings are saved (today's behavior unchanged), it prints a fixed panel:

```text
Setup complete. Settings written to ~/.config/llm/config.yaml.

Recommended next steps:
  1. llm doctor                  # verify cross-cutting prereqs
  2. llm runtime list            # see available runtimes
  3. llm runtime install <id>    # install one (e.g. `llm runtime install llamacpp`)
  4. llm model list              # browse model definitions
  5. llm model pull <id>         # download weights
  6. llm config validate         # check launch configs
  7. llm serve <config-id>       # start a server
```

### 5.8 Requirements integration

`requirements.yaml` (top-level) holds only cross-cutting deps: python, git, curl, huggingface-cli, build-essential. Per-runtime deps live in each runtime's `manifest.yaml` under `requires:` (same entry schema as today's top-level — `verify`, `install_hint`, plus the new optional `when:`).

| Command | Scope |
|---|---|
| `llm doctor` | Universal + every currently-installed runtime's deps. |
| `llm doctor --runtime <id>` | Universal + one runtime's deps (used by install pre-flight). |
| `llm doctor --all` | Universal + every runtime in the repo (installed or not). |
| `llm doctor render-requirements` | Regenerates `requirements.md`: universal section + one section per runtime. |

## 6. Module / file layout

| Path | Role |
|---|---|
| `src/llm_cli/core/params.py` | **New.** Param-type system: parse, validate, default, prompt, render-to-env, path-template expansion, `when:` evaluation. |
| `src/llm_cli/core/install_record.py` | **New.** Read/write `.installed`; sha256 of `build.sh` and canonicalized schema; install-state query. |
| `src/llm_cli/core/registry.py` | Manifest loader returns a typed `RuntimeManifest` (id, official, requires, build_schema, serve_schema). `validate_config` validates `serve.params` against schema and emits the runtime-not-installed warning. |
| `src/llm_cli/core/doctor.py` | Scoped sweep (universal + installed) with `--runtime`/`--all` modes. |
| `src/llm_cli/commands/runtime_cmd.py` | **New.** Typer sub-app: `list / info / install / uninstall / rebuild`. |
| `src/llm_cli/commands/model_cmd.py` | **New.** Typer sub-app: `list / info / pull`. |
| `src/llm_cli/commands/artifacts.py` | **Deleted.** Functions move into the two sub-apps. |
| `src/llm_cli/commands/serve.py` | Add `.installed` gate; build env from validated `serve.params`. |
| `src/llm_cli/commands/setup.py` | Append the "Recommended next steps" panel. |
| `src/llm_cli/commands/list_cmd.py` | Update `llm list runtimes` and `llm list models` to use the new schema/status fields. |
| `src/llm_cli/main.py` | Remove top-level `build` and `pull`; mount `runtime` and `model` sub-apps. |
| `runtimes/llamacpp/manifest.yaml` | Replace with the schema-bearing version (5.1). |
| `runtimes/llamacpp/build.sh` | Read `LLM_BUILD_FLAVOR` / `LLM_BUILD_JOBS`; flavor selects CMake flags. |
| `runtimes/llamacpp/verify.sh` | **New.** `exec "$LLM_RUNTIMES/llamacpp/llama.cpp/build/bin/llama-server" --version`. |
| `runtimes/llamacpp/serve.sh` | Keep `LLM_LLAMACPP_*` env names; align with `serve:` schema's `env:` fields. |
| `runtimes/stub-runtime/manifest.yaml` | Add empty `build: {}` and `serve: {}`. |
| `runtimes/stub-runtime/verify.sh` | Optional; if added, `exit 0`. |
| `configs/llamacpp__unsloth-qwen3.6-35b-a3b__default.yaml` | Convert `serve.env` → `serve.params` (5.4). |
| `configs/stub-runtime__stub-model__default.yaml` | Same conversion; `serve.params: {}`. |
| `docs/add-a-runtime.md` | Rewritten around the manifest schema and the four-script contract. |
| `docs/add-a-model.md` | Note that model schema is a follow-up; pull.sh contract unchanged. |
| `docs/runtime-lifecycle.md` | **New.** Install / rebuild / uninstall semantics; `.installed` record; drift behavior. |
| `README.md` | Update CLI table; replace `llm build` / `llm pull` with the new sub-apps; update Getting Started. |

## 7. Testing

### 7.1 Unit

- `params.py`: parse + validate each type; default fill; required-missing error; `path` token expansion (including unknown-token rejection); env-name derivation; `when:` evaluation.
- `install_record.py`: round-trip; sha256 stability across newlines; missing-file → not installed; corrupt-file → not installed + clear error.
- `registry.py`: manifest with schema loads; missing `serve:` key tolerated (empty); `validate_config` rejects unknown / missing / mistyped `serve.params`; emits warning for uninstalled runtime.
- `doctor.py`: scoped view returns only installed runtimes' deps; `--all` returns every runtime; `--runtime <id>` honors `when:` against supplied build params.

### 7.2 Integration (against `stub-runtime`)

- `llm runtime install stub-runtime --yes` → `.installed` created; `llm runtime list` shows it; `llm runtime info stub-runtime` renders cleanly.
- `llm config validate` is silent for an installed runtime's config; warns for an uninstalled one.
- `llm serve <stub-cfg>` refuses with the hint when not installed; succeeds after install.
- `llm runtime uninstall stub-runtime` removes the marker; serve refuses again.
- `llm runtime rebuild stub-runtime` re-installs with the same params; `--reset` re-prompts.
- `llm runtime install` with `--param flavor=cpu` for llamacpp avoids the `nvcc` requirement check (mocked doctor); `--param flavor=cuda` triggers it.

### 7.3 CLI surface tests

- `llm build` and `llm pull` are not registered (typer raises usage error).
- `llm runtime` and `llm model` sub-apps register the expected verbs.

### 7.4 Mock vs real

- WSL bash invocations stay behind the existing runner with an injectable subprocess fake (mirrors lifecycle test strategy).
- Real build (llama.cpp) is **not** exercised in CI; covered by manual smoke after the spec lands.

## 8. Documentation updates

- New: `docs/runtime-lifecycle.md` — install / rebuild / uninstall, the four-script contract, the `.installed` record, drift indicators.
- Rewrite: `docs/add-a-runtime.md` — manifest schema walk-through, dep declaration, when-clauses, verify.sh examples for common stacks.
- Update: `docs/add-a-model.md` — note model schema is a follow-up; pull.sh contract unchanged.
- Update: `README.md` — replace `llm build` / `llm pull` rows with `llm runtime ...` / `llm model ...` tables; refresh Getting Started to walk through `llm runtime install llamacpp` → `llm model pull <id>` → `llm serve`.
- Update: `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md` — add a note at the top pointing at this spec and the lifecycle spec.
- Update: `docs/lifecycle.md` — note the new `.installed` gate ahead of any serve.

## 9. Open questions (not blockers)

1. **`extra_args` escape hatch on serve params.** Keeping `type: string` with a doc warning is the v1 stance; auto-shell-splitting is the user's responsibility inside `serve.sh`. Revisit if it bites.
2. **`build.sh` sha drift behavior.** Informational only in v1; no warning at serve time. Promote to warning if it causes confusion.
3. **Uninstall default behavior.** v1 leaves built artifacts (only the marker is removed). `--purge` is the explicit destructive option. Revisit if leftover build trees become noisy.

## 10. Out of scope / future work

- **Model parameter schema** mirroring the runtime design (quant choice, files manifest, sha verification).
- **Multi-flavor coexistence** at the runtime level (install per `(runtime, flavor)` tuple).
- **Remote runtime catalog / download.**
- **Schema migration tooling** (renaming a `build:` param without forcing a `--reset`).
- **Webui** that consumes the schemas as forms (the whole point of this spec, but a separate effort).
