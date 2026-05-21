# LocalLLM Wizards, Recommendations & `loco advisor`

_Date: 2026-05-18_
_Status: Approved by user, ready for implementation planning_

## 1. Purpose

After 0.1.0 the CLI can already build runtimes, pull models, validate configs, and serve any of them in three modes. What it cannot do is **walk a user through assembling these pieces**. The only friction left in the zero-to-serving path is the YAML config that wires a runtime to a model, and the rigid four-script contract for authoring a custom (non-official) runtime. Both require opening an editor.

This spec adds **schema-driven interactive wizards** for the two manual steps, plus a thin **`loco advisor`** that surfaces VRAM-aware recommendations from machine specs. The new commands sit alongside the existing one-shot commands — nothing is replaced — and every wizard has a non-interactive flag-form sibling so scripting still works.

## 2. Problems solved

- **Config authoring is the loudest remaining manual step.** Today the user must hand-author `configs/<runtime>__<model>__<preset>.yaml` and know the runtime's `serve.params` schema, the naming convention, and the `${model_path}` templating. There is no generator.
- **Authoring a custom runtime is the wrong abstraction.** Today's "drop four scripts and a manifest" assumes the user wants `loco` to build their runtime from source. The far more common case is "I already have vLLM installed; I just want `loco` to manage start/stop/switch." The four-script + build-schema contract turns that into 30 minutes of scaffolding.
- **The CLI doesn't help with system-aware defaults.** `loco specs` already collects VRAM and GPU info, but no command uses it. Users guess `ctx` and `n_gpu_layers` by trial-and-error.
- **The runtime manifest co-locates two concerns.** Today's `runtimes/<id>/manifest.yaml` mixes runtime identity / build / dependencies (install-time concerns) with the serve-time parameter schema (config-facing contract). Both an interactive wizard and an eventual webui want the second concern in its own file, with the same shape regardless of `kind`.
- **Sequential one-shot commands give no end-to-end on-ramp.** A first-time user runs six independent commands with nothing chaining them. There's no single entrypoint that walks them through "settings → runtime → model → config → serve" while still skipping any step they've already done.

## 3. Goals

- One interactive command per remaining manual step: `loco runtime setup`, `loco config setup`. Existing one-shot commands (`loco runtime install`, etc.) are unchanged.
- One non-interactive sibling for the new config flow: `loco config new --runtime X --model Y --param k=v …`, sharing the wizard's code path.
- One advisor: `loco advisor`, in three forms (interactive, against a config id, with `--runtime`/`--model` flags), with `--json` for scripting.
- Extend `loco setup` to optionally chain into the new wizards (Y/n at each step), threading ids forward. `--default` keeps today's non-interactive behavior.
- Split `runtimes/<id>/manifest.yaml`'s `serve:` section into a standalone `runtimes/<id>/params.yaml`, the same shape for **both** official and custom runtimes. Add `tier:` and `description:` per param so the wizard can show a common-vs-advanced split with helpful labels.
- Add `kind: official | custom` to runtime manifests. `kind: custom` runtimes skip `build.sh` + `verify.sh` entirely; the wizard auto-generates a default `healthcheck.sh`.
- VRAM-aware recommendations for `llamacpp` only (in v1) — narrow, hard-coded, always labeled `(estimate)`.
- Hybrid TUI: `questionary` (arrow-key pickers) for selection-heavy steps; Rich prompts for typed value entry; plain-prompt fallback for non-TTY.

## 4. Non-goals

- **No model browse / search.** `loco model pull <hf-url>` stays a passthrough to the HF CLI; users discover models on huggingface.co. No curated catalog, no HF API search, no interactive disambiguation of bare repos.
- **No interactive editing of existing configs.** `loco config edit <id>` is not added. Users either re-run `loco config setup` (overwriting) or hand-edit the YAML.
- **No inference smoke test after `loco serve`.** Healthcheck still only proves the OpenAI endpoint is reachable, not that the model produces sensible output. Out of scope.
- **No recommendation hook framework for non-llamacpp runtimes.** `core/recommendations.py` contains exactly one hard-coded llamacpp branch in v1. The function signature leaves room for more later, but a generic hook system is deferred.
- **No typed serve params for custom runtimes via the wizard.** Custom runtimes always emit a `params.yaml` with `extra_args: string` only. Users who want richer typed params for a custom runtime hand-edit the file later — the wizard does not prompt for additional param definitions.
- **No TUI for read-only commands.** `loco doctor`, `loco specs`, `loco runtime info`, `loco config show`, `loco list` stay as plain output.
- **No TUI for the existing `loco runtime install` build prompts.** Stays as today's Typer prompts. Could be questionary'd later for symmetry but is not in this scope.
- **No `--dry-run` flag on wizards.** Useful but deferred; trivial to add later.
- **No alias / nickname system for long config ids.**
- **No webui.** This spec is the CLI half of a two-spec arc; the webui is the next milestone and consumes the schemas + advisor JSON that this spec produces.

## 5. Architecture

### 5.1 Runtime manifest split

`runtimes/<id>/manifest.yaml` keeps everything **except** the `serve:` schema:

```yaml
id: llamacpp
display_name: llama.cpp (llama-server)
kind: official                       # NEW: official | custom (default 'official')
description: >
  Builds upstream llama.cpp and serves GGUF via /v1 (OpenAI-compatible).
accepts_formats: [gguf]

requires:
  - id: cmake
    verify: { cmd: cmake --version, version_regex: 'cmake version ([\d.]+)', min: "3.16" }
    install_hint: "apt install cmake"
  - id: nvcc
    when: { build.flavor: cuda }
    verify: { cmd: nvcc --version, version_regex: 'release ([\d.]+)', min: "12.0" }
    install_hint: "Install CUDA toolkit; see NVIDIA docs."

build:                                # forbidden when kind: custom
  flavor:
    type: enum
    values: [cuda, cpu, vulkan]
    default: cuda
    prompt: "Which backend to build?"
  jobs:
    type: int
    default: 0
    prompt: "Parallel build jobs (0 = nproc)"
```

`runtimes/<id>/params.yaml` is the **config-facing schema** — what configs may set in `serve.params`, what env vars get injected when spawning `serve.sh`:

```yaml
gguf_path:
  type: path
  required: true
  env: LLM_LLAMACPP_GGUF
  tier: common
  description: "Path to the GGUF weights file."

n_gpu_layers:
  type: int
  default: -1
  env: LLM_LLAMACPP_N_GPU_LAYERS
  tier: common
  description: "Layers to offload to GPU. -1 = all."

ctx:
  type: int
  default: 8192
  env: LLM_LLAMACPP_CTX
  tier: common
  description: "Context window in tokens."

extra_args:
  type: string
  default: ""
  env: LLM_LLAMACPP_EXTRA_ARGS
  tier: advanced
  description: "Pass-through flags appended to llama-server."
```

**Per-entry field schema for `params.yaml`:**

| Field | Required | Default | Purpose |
|---|---|---|---|
| `type` | yes | — | `string`, `int`, `float`, `bool`, `enum`, `path` |
| `required` | no | `false` | Hard error in `loco config validate` if config omits it |
| `default` | no | — | Pre-fills wizard; used at serve-time env-build for unset keys |
| `env` | no | `LLM_<RUNTIME_UPPER>_<KEY_UPPER>` | Env var injected when spawning `serve.sh` |
| `tier` | no | `common` | `common` or `advanced`; controls visibility in `loco config setup` |
| `description` | no | `""` | One-line text shown next to the wizard prompt and (later) UI tooltip |
| `values` | yes for `enum` | — | List of allowed enum values |

Path-template expansion (`${data_root}`, `${model_path}`, `${runtimes_dir}`, etc.) is unchanged — handled when building env vars from the resolved config.

**Asymmetry note.** Build params (`build:` in `manifest.yaml`) keep their existing `prompt:` field — a build prompt is often a question ("Which backend to build?"). Serve params in `params.yaml` use `description:` only; the key name is the prompt label. If we ever need a serve-time prompt override, we add it later.

### 5.2 `kind: official | custom`

Top-level field on `manifest.yaml`. Defaults to `official` for backward compatibility (existing manifests don't need to set it, though we make it explicit in the migration).

**`kind: custom` semantics:**

- `build:` section is **forbidden** (validation error if present).
- `requires:` is optional. Wizard offers to add user-supplied checks (e.g. `vloco --version`); empty list is fine.
- `params.yaml` contains only `extra_args` by default (wizard-generated). User may hand-edit later to add more typed params.
- No `build.sh` or `verify.sh` files exist on disk.
- A `healthcheck.sh` file is **auto-generated** by the wizard with a default OpenAI-endpoint probe.
- A `serve.sh` file is wizard-generated from either a template (the user supplies a single bash invocation line, we wrap in boilerplate) or an `$EDITOR` session. `$EDITOR` semantics: we write the boilerplate'd template to a temp file, invoke `$EDITOR <tmpfile>` (or `nano` if unset), wait for editor exit; on exit-0 the file contents become `serve.sh`, on any other exit the wizard aborts with no files written.
- `.installed` marker is written by the wizard immediately at end (no build to gate on). Shape preserved across kinds; `build_sh_sha256: null`, `verify_passed: null`, `schema_hash: <sha256 of params.yaml bytes>`.
- `loco runtime install <id>` and `loco runtime rebuild <id>` refuse to act on `kind: custom` runtimes (boundary errors in §5.7).

**Folder location.** Custom runtimes live under `runtimes/<id>/` in the repo, the same as official ones. `kind` is the distinguisher, not folder layout. They get committed to git so the user's setup is reproducible across machines.

### 5.3 Env contract for `serve.sh`

Two independent sources contribute env vars:

**A. Fixed CLI-policy vars** (set by the CLI regardless of `kind`, not declared in `params.yaml`):

| Var | When set | Source |
|---|---|---|
| `LLM_SERVE_HOST` | always | `config.serve.host` (default `127.0.0.1`) |
| `LLM_SERVE_PORT` | always | `config.serve.port` |
| `LLM_MODEL_PATH` | model is set on config | resolved `$LLM_MODELS/<id>/<artifact.primary>` |
| `LLM_MODEL_ID` | model is set on config | registry id |

**B. Param-driven vars** (from `params.yaml` `env:` field, uniform across kinds):

Each entry in `params.yaml` contributes one env var named by its `env:` field (or the derived `LLM_<RUNTIME_UPPER>_<KEY_UPPER>` if `env:` is absent). The wizard-generated `params.yaml` for custom runtimes uses `env: LLM_EXTRA_ARGS` for its single `extra_args` entry by convention; user-edited custom params.yamls can declare any env name they want. Official runtimes typically follow the `LLM_<RUNTIME>_<PARAM>` convention.

**C. Global env** (data_root, repo_root, runtimes_dir, models_dir, cache_dir) — set always, unchanged from today.

The default auto-generated `healthcheck.sh` for custom runtimes:

```bash
#!/usr/bin/env bash
set -euo pipefail
HOST="${LLM_SERVE_HOST:-127.0.0.1}"
curl -fsS -o /dev/null "http://${HOST}:${LLM_SERVE_PORT}/v1/models"
```

The user may edit this file later if a non-default probe is needed.

### 5.4 VRAM-aware recommendations

Lives in a new `core/recommendations.py` module. Single entry point:

```python
def recommend(runtime_id: str, param_key: str, *, model, specs) -> Recommendation | None: ...
```

v1 contains exactly one hard-coded `llamacpp` branch. The function returns `None` whenever any precondition fails — wizards then fall back silently to the schema's `default:`.

**Preconditions (all must hold):**

- Runtime is `llamacpp`.
- A model is set on the config-in-progress with a known `artifact.total_size_bytes`.
- `loco specs` detects ≥1 GPU with `vram_gb > 0`.

**Suggested `ctx`:**

```
HEADROOM_BYTES   = 1 << 30                                # 1 GB reserved for OS/CUDA
free_vram        = total_vram_bytes − HEADROOM_BYTES
available_for_kv = max(0, free_vram − weights_bytes)
suggested_ctx    = floor(available_for_kv / (2 << 20))    # ~2 MB/token, architecture-blind
suggested_ctx    = snap_pow2(suggested_ctx, min=2048)     # 2048, 4096, 8192, 16384, ...
```

If the model exceeds free VRAM, `available_for_kv` is 0, and the recommendation falls back to a conservative `4096` (so the user still gets *something* sensible when partial-offload is unavoidable).

**Suggested `n_gpu_layers`** (only when `weights_bytes > free_vram`):

```
if weights_bytes <= free_vram:  suggest -1
else:                           suggest floor((free_vram / weights_bytes) * 60)
                                # 60 is a heuristic layer count; reasonable for most LLMs
```

**Honesty:** the 2 MB/token figure is architecture-blind. True KV cost varies ~4× between GQA and full attention. The 60-layer heuristic for `n_gpu_layers` is similarly coarse. Recommendations are always rendered with `[estimate <value>: <reason>]` so users know they're approximations, and they remain free to override.

### 5.5 Hybrid TUI primitives (`core/wizards.py`)

A new module wraps all interactive I/O. It is the **only** place that imports `questionary`. The `select` / `checkbox` / `confirm` wrappers degrade to plain `rich.prompt.Prompt.ask`-based fallbacks (numbered-list selection for `select`, comma-separated indices for `checkbox`, `[y/N]` for `confirm`) when:

- `sys.stdout.isatty() is False`, or
- `$TERM` is unset / `""` / `"dumb"`, or
- `--quiet` is passed.

The `text` wrapper is already a thin shim over `rich.prompt.Prompt.ask` — same code path with or without TTY.

**Primitives provided:**

| Wrapper | Backed by | Purpose |
|---|---|---|
| `select(prompt, choices, default=None)` | `questionary.select` | Arrow-key list pick. |
| `checkbox(prompt, choices, default=())` | `questionary.checkbox` | Multi-select. |
| `confirm(prompt, default=True)` | `questionary.confirm` | Y/n. |
| `text(prompt, default=None, validate=None)` | `rich.prompt.Prompt.ask` | Typed entry. |
| `walk_tier(params, model, specs)` | composes above | Walks common-tier params; offers `confirm` to reveal advanced. |
| `review(rows, on_edit)` | `questionary.select` of rows + `[Save]`/`[Abort]` | Edit-loop until save/abort. |

All wrappers accept a `default` and an optional `validate` callable, and surface the user's answer as a plain Python value. Tests substitute a fake answers iterator at the module level.

### 5.6 `loco setup` chain orchestration

New module `core/chain.py`. Invoked by `loco setup` (non-`--default` path) after the existing settings block is written. Steps, in order:

1. **Install a runtime now?** Y/n. If Y → invoke `loco runtime setup`; capture returned `runtime_id`.
2. **Pull a model now?** Single prompt: *"Hugging Face URL (or empty / `n` to skip):"*. If user supplies a URL, invoke `loco model pull <url>` and capture returned `model_id`. Empty input or `n` skips this step. (Collapsed into one prompt rather than Y/n-then-URL to save a keystroke.)
3. **Create a config now?** Y/n. If Y → invoke `loco config setup` with `--runtime <runtime_id>` and `--model <model_id>` flags pre-filled from prior steps (omitted if the prior step was skipped); capture returned `config_id`.
4. **Start serving this config?** Y/n. If Y → invoke `loco serve <config_id>` in background mode.

**Skip semantics:** "no" to any step skips just that step and continues to the next. The chain never aborts on a "no."

**Failure semantics:** if an explicit-Y step fails (sub-command exits non-zero), the chain **aborts** with a non-zero exit. We don't silently swallow user-requested failures.

**Threading:** ids returned by sub-commands flow forward as flag values. Any sub-command that produces an id exposes it as the last line of its non-`--json` output (already true for `loco runtime install` and `loco model pull`; new for `loco runtime setup` and `loco config setup`). Chain logic parses that line; sub-commands also return the id via their Typer command function for in-process composition.

### 5.7 Command surface

**New commands in 0.2:**

| Command | Role |
|---|---|
| `loco setup` *(extended)* | After writing settings, asks Y/n to chain into runtime setup → model pull → config setup → serve. `--default` keeps non-interactive behavior. |
| `loco runtime setup` | Interactive wizard. Branches into **preset** (delegates to existing `loco runtime install <id>`) or **custom** (authors a no-build runtime from a bring-your-own `serve.sh`). |
| `loco config setup` | Schema-driven wizard: pick runtime → pick model (compat-filtered via `accepts_formats`) → walk `serve.params` (common, then `[a]dvanced` reveal) → name. |
| `loco config new --runtime X --model Y --preset N [--param k=v …] [--port N]` | Non-interactive sibling for scripting. Same code path as the wizard, no prompts. |
| `loco advisor` | Three forms: interactive (pick runtime + model), positional (advise an existing config), and flag form (`--runtime X --model Y`). `--json` available for any form. |

**Unchanged:**

- All `.installed` semantics, `state/running.json`, `state/history.jsonl` formats, model registry, settings format.
- `loco doctor`, `loco specs`, `loco runtime install|info|list|uninstall|rebuild`, `loco model pull|add|list|info|uninstall`, `loco serve|stop|switch|status|logs`, `loco config show|validate` (validate is extended in §5.10 but the command surface is unchanged).

**Boundary errors:**

| Scenario | Behavior |
|---|---|
| `loco runtime install <id>` where `manifest.kind == 'custom'` | Error: *"runtime `<id>` is custom; use `loco runtime setup` to re-author. Custom runtimes have no build step."* |
| `loco runtime rebuild <id>` where `kind == 'custom'` | Error: *"rebuild applies to official runtimes only."* |
| `loco runtime setup` where `runtimes/<id>/manifest.yaml` already exists on disk | Error: *"runtime `<id>` already exists. `loco runtime uninstall <id> --purge` first, or pick a different id."* (Detection is folder-presence, not `.installed`.) |
| `loco config setup --runtime <id>` for a runtime id that doesn't exist | Error: *"no runtime named `<id>`"* (don't silently fall back to picker — the flag was an explicit assertion). |
| `loco config setup --model <id>` for a model id that doesn't exist | Error: *"no model named `<id>` in registry."* |
| `loco advisor <config-id>` for a config that doesn't exist | Standard "not found" error with did-you-mean suggestion. |
| `loco advisor --json` (any form) | The `[c] create a config` bonus chain is suppressed — JSON mode is for scripting. |
| `loco config setup` runtime picker, user picks an `[not installed]` entry | Allowed (matches the existing `loco config validate` warn-and-pass behavior for uninstalled runtimes). Wizard prints an inline yellow warning *"runtime `<id>` is not installed; `loco serve` will refuse until you run `loco runtime setup`"* and continues. The config is saved normally. |
| `loco config setup` runtime picker when zero runtimes are discovered at all (no folders) | Hard error: *"no runtimes found in `runtimes/`. Try `loco runtime setup`."* |
| `loco config setup` model picker when zero compatible models | Hard error: *"no models in registry match `accepts_formats: [...]`. Try `loco model pull <hf-url>`."* |

### 5.8 `loco advisor`

Surface:

```text
loco advisor                                # interactive: pick runtime → pick model → advise
loco advisor <config-id>                    # advise against an existing config
loco advisor --runtime X --model Y          # non-interactive composed advice
[any of the above]  [--json]               # JSON output for any form
```

**Validation:**

- `--runtime` and `--model` are all-or-nothing. One without the other → error.
- Positional `<config-id>` combined with `--runtime`/`--model` → error.
- `<config-id>` that doesn't resolve → standard "not found" error.

**Interactive flow (`loco advisor` with no args):**

1. Numbered runtime picker (lists all discovered runtimes; marks each `[installed]` or `[not installed]`; shows `description`).
2. Numbered model picker (filtered by chosen runtime's `accepts_formats`; if `accepts_formats: []`, this step is skipped — no model needed).
3. Render advice.

**Text output (example):**

```text
Recommendations for llamacpp + qwen-7b-q4 on this machine
GPU: NVIDIA RTX 4090 (24 GB)

  ctx           suggested 16384
                24 GB VRAM − 18 GB weights ≈ 3k tokens of KV cache

  n_gpu_layers  suggested -1
                Model fits entirely in VRAM

Notes:
  • Estimates based on llama.cpp's typical KV cost; actual VRAM use varies
    with quant and prompt length.
  • Run  loco config setup  to scaffold a config using these values.
```

**`--json` output:**

```json
{
  "runtime": "llamacpp",
  "model": "qwen-7b-q4",
  "machine": { "gpus": [{"name": "NVIDIA RTX 4090", "vram_gb": 24}] },
  "recommendations": {
    "ctx":           { "value": 16384, "reason": "24 GB VRAM − 18 GB weights → ~3k KV tokens" },
    "n_gpu_layers":  { "value": -1,    "reason": "Model fits in VRAM" }
  }
}
```

**Bonus chain (non-JSON, interactive sessions only):**

```text
[c] create a config with these values   [enter] done
> 
```

If `[c]`: drops into `loco config setup` with `--runtime`, `--model`, and the suggested param values pre-filled (the user still walks the wizard to confirm or edit). Suppressed in `--json` mode.

`loco config setup` calls into the same recommendations module, so values shown in the wizard and values from `loco advisor` always agree.

### 5.9 Wizard rendering specifics

**Param with a recommendation (3 lines):**

```text
ctx — Context window in tokens.
  suggested 16384  (24 GB VRAM − 18 GB weights ≈ 3k KV tokens)
ctx [16384]: 
```

**Param without a recommendation (2 lines, common case):**

```text
n_gpu_layers — Layers to offload to GPU. -1 = all.
n_gpu_layers [-1]: 
```

Styling (Rich): key in **bold cyan**; em-dash + description in default color; `suggested NNNN` in **bold green**; reason in dim italics; `[default]:` is Rich's native prompt-default syntax.

**Section dividers in `loco config setup`:**

```text
─── Runtime params (common) ──────────────────────────────
  [walks the common params]

─── 5 advanced params hidden  (type 'a' to reveal, enter to skip) ──
> 
```

**Review screen (questionary `select` of rows):**

```text
? Review — navigate to a row to edit, or save

❯ [Save and write file]
  ─────
  runtime         llamacpp
  model           unsloth-qwen3.6-35b-a3b__ud-q4-k-xl
  preset          default
  port            8080
  gguf_path       ${model_path}
  n_gpu_layers    41
  ctx             4096
  ─────
  [Abort without saving]
```

Arrow to any field → enter → re-prompts that single field with current value pre-filled → returns to review. Arrow to `[Save]` → writes files. Arrow to `[Abort]` → exits with no files written.

### 5.10 `loco config validate` extensions

All existing rules from `2026-05-17-runtime-manifest-and-installs.md` still apply. Additions:

| Rule | Result |
|---|---|
| Runtime manifest still contains a top-level `serve:` key (pre-migration shape) | Hard error: *"serve: schema moved to params.yaml; move the keys to that file."* |
| `manifest.kind == 'custom'` AND `manifest.build:` present | Hard error. |
| `params.yaml` missing or empty | Treated as `{}` (no params). No warning. |
| `params.yaml` entry with `type: enum` and no `values:` | Hard error. |
| `params.yaml` entry with `tier:` not in `{common, advanced}` | Hard error. |
| `params.yaml` entry with `required: true` AND `default:` set | Warning (`required + default is redundant; default ignored`). |
| Unknown top-level fields in `manifest.yaml` or in any `params.yaml` entry | Warning + ignore. |
| Keys in `config.serve.params` that aren't in `params.yaml` | Hard error (existing behavior; restated for completeness). |

### 5.11 Wizard error handling

- **Atomic file writes.** All emissions (`manifest.yaml`, `params.yaml`, `serve.sh`, `healthcheck.sh`, `configs/<id>.yaml`, `.installed`) use `tmp + os.replace`. No partial state on failure.
- **In-memory staging.** Every wizard collects answers in memory; files are written only at final confirmation. Ctrl-C / `[Abort]` = nothing written.
- **Doctor failure during custom-runtime wizard.** If `loco doctor --runtime <id>` fails *after* wizard completion, files + `.installed` are still written and a clear warning is printed. The existing `.installed` serve-gate keeps `loco serve` from running anyway if prereqs are truly missing at serve time — but the manifest is registered so the user can fix prereqs and proceed without re-running the wizard.
- **Port-in-use during config setup.** Wizard suggests next free port; user confirms. If the user manually enters a taken port, validation accepts it (validation isn't a port-check); the existing port probe in `loco serve` fails fast at start time.

### 5.12 History events

`state/history.jsonl` gains new event kinds:

```json
{ "ts": "...", "action": "runtime-setup",  "id": "vllm-custom", "kind": "custom" }
{ "ts": "...", "action": "config-create",  "id": "llamacpp__qwen__default", "via": "setup" | "new" }
{ "ts": "...", "action": "setup-chain",    "steps": ["runtime-setup","model-pull","config-create","serve"] }
{ "ts": "...", "action": "advisor",        "runtime": "...", "model": "...", "from": "interactive"|"flags"|"config" }
```

Existing event kinds (`runtime-install`, `runtime-uninstall`, `runtime-rebuild`, `start`, `stop`, `switch`, `systemd-write`, `reap-stale`) are unchanged.

## 6. CLI flows

### 6.1 `loco setup` chain end-to-end

```text
$ loco setup
─── Settings ─────────────────────────────────────────────
data_root [~/llm]: 
[... existing settings prompts ...]
wrote ~/.config/llm/config.yaml

─── Install a runtime now? ───────────────────────────────
Skip if you've already installed the runtime you want.
> [Y/n] 
[delegates to: loco runtime setup → captures <runtime-id>]

─── Pull a model now? ────────────────────────────────────
Hugging Face URL (or 'n' to skip):
> [enter to skip / paste url]
[delegates to: loco model pull <url> → captures <model-id>]

─── Create a config now? ─────────────────────────────────
> [Y/n] 
[delegates to: loco config setup --runtime <id> --model <id>]

─── Start serving this config? ───────────────────────────
> [Y/n] 
[delegates to: loco serve <config-id>]

─── Done ─────────────────────────────────────────────────
Setup complete. [If serve happened:  Use  loco status  to see what's running.]
                [Else:               Next:  loco serve <config-id>  when ready.]
```

### 6.2 `loco runtime setup` — custom branch

```text
$ loco runtime setup

─── Runtime setup ───────────────────────────────────────
  [1] Preset — install an official runtime (we build it)
  [2] Custom — register a runtime you already have installed elsewhere
  [a] Abort
> 2

─── Custom runtime ─────────────────────────────────────
Runtime id (slug, e.g. 'vllm-custom'): > vllm-custom
Display name [vllm-custom]:                > vLLM (user-installed)
Accepts which model formats?
  [ ] gguf
  [x] safetensors-dir
  [ ] none (no model needed)
> [enter when done]

Serve command — [t]emplate (we wrap in bash) / [e]ditor (full control)
> t

The CLI will inject: LLM_SERVE_HOST, LLM_SERVE_PORT, LLM_MODEL_PATH, LLM_EXTRA_ARGS
Bare invocation line (we add the bash boilerplate):
> vloco serve "$LLM_MODEL_PATH" --host "$LLM_SERVE_HOST" --port "$LLM_SERVE_PORT" $LLM_EXTRA_ARGS

Add a 'requires:' check? (skip if not needed)
> [enter to skip / type command, e.g.] vloco --version
  version regex:    > ([\d.]+)
  minimum version:  > 0.8.0
  install hint:     > pip install vllm

Run loco doctor --runtime vllm-custom to verify? [Y/n] > 
[runs doctor, prints pass/fail per check]

wrote runtimes/vllm-custom/manifest.yaml
wrote runtimes/vllm-custom/serve.sh         (executable)
wrote runtimes/vllm-custom/healthcheck.sh   (executable, default OpenAI probe)
wrote runtimes/vllm-custom/params.yaml      (extra_args only)
wrote $LLM_RUNTIMES/vllm-custom/.installed

Next: loco config setup --runtime vllm-custom
```

### 6.3 `loco config setup` end-to-end

```text
$ loco config setup

─── Pick a runtime ─────────────────────────────────────
  [1] llamacpp        [installed]    Accepts: gguf
  [2] vllm-custom     [installed]    Accepts: safetensors-dir
  [3] stub-runtime    [installed]    Accepts: (none)
> 1

─── Pick a model ───────────────────────────────────────
Showing models compatible with llamacpp (format: gguf)
  [1] unsloth-qwen3.6-35b-a3b__ud-q4-k-xl     35.2 GB  Q4_K_XL
  [2] thebloke-tinyllama-1.1b__q4-k-m          0.6 GB  Q4_K_M
> 1

─── Runtime params (common) ────────────────────────────
gguf_path — Path to the GGUF weights file.
gguf_path [${model_path}]: 

n_gpu_layers — Layers to offload to GPU. -1 = all.
  suggested 41  (24 GB VRAM − 35 GB weights → partial offload)
n_gpu_layers [41]: 

ctx — Context window in tokens.
  suggested 4096  (model exceeds VRAM; conservative default)
ctx [4096]: 

─── 1 advanced param hidden  (type 'a' to reveal, enter to skip) ──
> 

─── Serving ────────────────────────────────────────────
host [127.0.0.1]: 
port [8080]:                          (8080 is free)

─── Naming ─────────────────────────────────────────────
preset [default]: 
config id (auto): llamacpp__unsloth-qwen3.6-35b-a3b__default

─── Review ─────────────────────────────────────────────
  runtime    llamacpp
  model      unsloth-qwen3.6-35b-a3b__ud-q4-k-xl
  preset     default
  port       8080
  params:
    gguf_path      ${model_path}
    n_gpu_layers   41
    ctx            4096
    extra_args     (empty)

  [s] save   [e] edit a value   [a] abort
> s

wrote configs/llamacpp__unsloth-qwen3.6-35b-a3b__default.yaml

Next: loco serve llamacpp__unsloth-qwen3.6-35b-a3b__default
```

### 6.4 `loco config new` (non-interactive sibling)

```bash
loco config new \
  --runtime llamacpp \
  --model unsloth-qwen3.6-35b-a3b__ud-q4-k-xl \
  --preset default \
  --port 8080 \
  --param gguf_path='${model_path}' \
  --param n_gpu_layers=-1 \
  --param ctx=16384
```

- `--runtime` required.
- `--model` required if runtime's `accepts_formats` is non-empty; forbidden if empty.
- `--preset` defaults to `default`.
- `--port` defaults to schema default or `8080`.
- `--param k=v` repeatable. Missing required schema params → error listing them. Unknown params → error.
- Overwrite-existing prompts (Y/n) unless `--force`.

### 6.5 `loco advisor` worked example

```text
$ loco advisor llamacpp__unsloth-qwen3.6-35b-a3b__default

Recommendations for llamacpp + unsloth-qwen3.6-35b-a3b__ud-q4-k-xl
GPU: NVIDIA RTX 4090 (24 GB)

  ctx           suggested 4096
                model 35 GB > free VRAM 23 GB; conservative default

  n_gpu_layers  suggested 41
                approx 60-layer model × (23 GB / 35 GB) ≈ 39, rounded up

Notes:
  • Estimates based on llama.cpp's typical KV cost; actual VRAM use varies
    with quant and prompt length.
  • Run  loco config setup  to scaffold a config using these values.

[c] create a config with these values   [enter] done
> 
```

## 7. Module / file layout

### 7.1 Repo files (one-time migration in this commit)

| File | Change |
|---|---|
| `runtimes/llamacpp/manifest.yaml` | Remove `serve:`; add `kind: official`. |
| `runtimes/llamacpp/params.yaml` | **New.** Extracted serve schema + `tier:` + `description:` per entry. |
| `runtimes/stub-runtime/manifest.yaml` | Remove `serve: {}`; add `kind: official`. |
| `runtimes/stub-runtime/params.yaml` | **New.** Empty (or omitted entirely — both equivalent). |

Auto-generated by `loco runtime setup` custom branch (per custom runtime, not in this commit):

- `runtimes/<id>/manifest.yaml` (kind: custom)
- `runtimes/<id>/serve.sh` (executable)
- `runtimes/<id>/healthcheck.sh` (executable, default OpenAI probe)
- `runtimes/<id>/params.yaml` (just `extra_args` by default)

Existing configs (`configs/*.yaml`) need no shape change.

### 7.2 Python modules (`src/llm_cli/`)

| Path | Change | Role |
|---|---|---|
| `core/params.py` | Modified | Accept `tier` + `description` fields. |
| `core/registry.py` | Modified | Load `params.yaml` alongside `manifest.yaml`; reject pre-migration `serve:` shape; `validate_config` walks new schema. |
| `core/install_record.py` | Modified | Support `kind: custom` records (`build_sh_sha256: null`, `verify_passed: null`, `schema_hash = sha256 of params.yaml bytes`). |
| `core/recommendations.py` | **New** | VRAM recommendation logic. Single `recommend(runtime_id, param_key, *, model, specs)` entry point with one llamacpp branch. |
| `core/wizards.py` | **New** | Hybrid TUI primitives (questionary wrappers + plain fallback + tier walker + review screen). The only module importing `questionary`. |
| `core/chain.py` | **New** | `loco setup` chain orchestration. |
| `commands/setup.py` | Modified | Invoke `core.chain` after settings write unless `--default`. |
| `commands/runtime_cmd.py` | Modified | Add `setup` subcommand (preset + custom branches). Refuse `install`/`rebuild` on `kind: custom`. |
| `commands/config_cmd.py` | Modified | Add `setup` + `new` subcommands. Extend `validate` per §5.10. |
| `commands/advisor.py` | **New** | `loco advisor` top-level command (3 forms + `--json`). |
| `commands/serve.py` | Unchanged | Existing `.installed` gate works uniformly across kinds. |
| `main.py` | Modified | Mount new subcommands; mount `loco advisor` at top level. |

### 7.3 New dependencies (`requirements.txt`)

- `questionary` (~2.0)
- `prompt_toolkit` (transitive of questionary; pin only if a specific version is required)

No other new runtime deps.

## 8. Testing

### 8.1 Unit

- `core/params.py` — `tier` / `description` parsing; validation rules from §5.1 fire (enum-no-values, bad tier value, required+default warning, etc.).
- `core/registry.py` — split-files loading; missing `params.yaml` = empty; old-shape manifest with `serve:` rejected with clear message.
- `core/install_record.py` — custom-kind record round-trips; `schema_hash` computed from `params.yaml` bytes; sha stable across line endings.
- `core/recommendations.py` — llamacpp branch returns expected values for representative `(vram_gb, weights_gb)` pairs; returns `None` for non-llamacpp, missing model size, no-GPU specs.
- `core/wizards.py` — tier walker yields common-then-advanced; review-screen edit-loop terminates on save/abort; plain-prompt fallback used when stdin is not a TTY.
- `core/chain.py` — Y/n skip doesn't abort; sub-step failure aborts non-zero; id threading pre-fills next sub-wizard.

### 8.2 Integration (against `stub-runtime`)

All `questionary` calls mocked at the `core.wizards` layer with a fake answers iterator.

- `loco config validate` — passes for new params.yaml shape; errors on missing required, unknown keys, wrong types.
- `loco runtime setup` custom (template mode) — writes 4 files + `.installed`; manifest has `kind: custom`; `params.yaml` has only `extra_args`.
- `loco runtime setup` preset — delegates to install; produces same artifacts as direct `loco runtime install <id>`.
- `loco config setup` end-to-end — pre-fill from flags works; review-and-save writes a valid config that round-trips through `loco config validate`.
- `loco config new --runtime X --model Y --param k=v` — output identical to wizard with same inputs (snapshot compare).
- `loco advisor` (all three forms, text + JSON) — produces expected output.
- `loco setup` chain (all-Y path) — runs through all four sub-steps; captures returned ids correctly.
- `loco setup` chain with a sub-step failure — aborts with non-zero exit.

### 8.3 CLI surface

- New commands register and appear in `--help`.
- `loco runtime install <custom-id>` exits 1 with the §5.7 boundary message.
- `loco runtime rebuild <custom-id>` exits 1.

### 8.4 Mock vs real

- All `questionary` interactions go through `core/wizards.py`; tests substitute a fake.
- WSL bash invocations stay behind the existing runner + injectable subprocess fake.
- No real network in CI; HF API client mocked. No real `nvidia-smi`; specs detection mocked with synthetic GPU profiles.

## 9. Documentation updates

- **New** `docs/wizards.md` — overview of the 4 new commands, when to use wizard vs one-shot, sample transcripts of the TUI pickers.
- **New** `docs/add-a-recommendation.md` — single-page guide for adding per-runtime recommendation branches in `core/recommendations.py`.
- **Rewrite** `docs/add-a-runtime.md` — preset path = "nothing to author, just `loco runtime install <id>`"; custom path = "use `loco runtime setup`; here's the resulting `params.yaml` + `serve.sh` if you want to hand-edit later."
- **Update** `docs/add-a-config.md` — recommend `loco config setup` as the primary flow; document `loco config new` for scripting; hand-authoring still supported.
- **Update** `docs/runtime-lifecycle.md` — note `kind: custom` skips `build.sh`/`verify.sh`; `.installed` is written by the wizard directly.
- **Update** `README.md` — Getting Started leads with `loco setup` (chain) for first-timers; granular CLI table preserved.
- **Update** `docs/superpowers/specs/2026-05-17-runtime-manifest-and-installs.md` — add a note at the top: "`params.yaml` split + `kind: custom` are designed in `2026-05-18-wizards-and-advisor.md`."

## 10. Migration

In a single PR/commit:

1. Split `runtimes/llamacpp/manifest.yaml` → `manifest.yaml` (sans `serve:`) + new `params.yaml` (with `tier:` + `description:` per entry).
2. Add `kind: official` to `llamacpp` and `stub-runtime` manifests.
3. Remove `serve: {}` from `stub-runtime/manifest.yaml`. (Create empty `params.yaml` or omit — equivalent.)
4. Update `core/registry.py` to load both files; reject old shape with clear message.
5. Existing `.installed` files: **no forced rewrite.** Their `schema_hash` becomes stale on next `loco runtime info`, which surfaces the existing drift warning (*"schema changed since install; rebuild to refresh"*) — correct behavior. Users may optionally run `loco runtime rebuild llamacpp --reset`; no functional impact if they don't.
6. Existing `configs/*.yaml` — no edits required.
7. Apply doc updates from §9.

**User-side migration:** none required beyond an optional `loco runtime rebuild` to clear the schema-drift indicator.

## 11. Open questions (not blockers)

1. **VRAM heuristic accuracy.** The 2 MB/token figure and 60-layer assumption are deliberately coarse for v1. If users report consistently bad estimates for a specific architecture family (e.g., MoE), tighten with a small per-architecture lookup table — but keep this out of v1 to avoid over-engineering.
2. **Editor escape hatch in custom-runtime wizard.** The `[t]emplate / [e]ditor` branch covers both fast and full-control paths. Watch whether `[e]` is used in practice; if essentially never, drop it.
3. **`loco runtime setup` for existing official IDs.** Currently errors with "use `loco runtime install`." Could instead detect kind and delegate. Not done in v1 to keep behavior predictable; revisit if it surprises users.
4. **Should `loco advisor --json` accept `--save <path>`?** Minor convenience; deferred.

## 12. Out of scope / future work

- **Model browse / search / curated catalog.** Deferred indefinitely; HF is the catalog.
- **Inference smoke test after `loco serve`.** Worth doing later as a separate `loco test <config>` or post-readiness probe; not in 0.2.
- **Recommendation hook framework for non-llamacpp runtimes.** Add per-runtime branches in `core/recommendations.py` as new runtimes get added.
- **TUI for read-only commands.** Live status, recent history, etc. Could be a `loco tui` dashboard — but that's the webui's territory.
- **TUI for the existing `loco runtime install` build prompts.** Symmetry-only; defer.
- **`loco config edit <id>` interactive editing of existing configs.** Add when a user actually asks.
- **`--dry-run` flag on wizards.** Trivial to add later; defer until requested.
- **Alias / nickname system for long config ids.**
- **Webui.** The next milestone after this spec ships. The schemas, the JSON contract from `loco advisor`, and the recommendations module are deliberately webui-shaped.

## 13. Cross-references

- Runtime manifests this builds on: [`2026-05-17-runtime-manifest-and-installs.md`](2026-05-17-runtime-manifest-and-installs.md).
- Model registry this builds on: [`2026-05-17-models-registry-redesign.md`](2026-05-17-models-registry-redesign.md).
- Settings & setup this extends: [`2026-05-17-settings-and-setup-redesign.md`](2026-05-17-settings-and-setup-redesign.md).
- Serve / stop / switch lifecycle (unchanged): [`2026-05-17-lifecycle-and-serve.md`](2026-05-17-lifecycle-and-serve.md).
- Original layout: [`2026-05-15-localllm-scaffolding-design.md`](2026-05-15-localllm-scaffolding-design.md).
