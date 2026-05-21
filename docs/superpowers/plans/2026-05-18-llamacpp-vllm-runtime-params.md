# llamacpp & vllm Runtime Params Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exhaustive tiered build/serve schemas for **llamacpp**, a new official **vllm** runtime (pip/venv), and **`bind: model_path`** so config setup never prompts for weights paths when a model is already chosen.

**Architecture:** Extend `ParamSpec` with `bind`, add `apply_model_bindings()` used by `do_config_setup` / `do_config_new`. Expand `runtimes/llamacpp/` catalogs and scripts; add `runtimes/llm_cli`-style mapping in `serve.sh` via shared bash helpers. Ship `runtimes/vllm/` as a second official package. Tier-aware interactive **runtime install** reuses `walk_tier()` for build params.

**Tech Stack:** Python 3.11+, Typer, Rich, questionary, PyYAML, pytest, bash (WSL scripts).

**Reference spec:** [`docs/superpowers/specs/2026-05-18-llamacpp-vllm-runtime-params-design.md`](../specs/2026-05-18-llamacpp-vllm-runtime-params-design.md)

**Running tests** (from repo root, WSL or Windows venv):

```bash
python -m pytest tests -q
```

**Locked decisions** (do not revisit):

- `bind: model_path` auto-value is always the literal string `${model_path}`.
- llamacpp default `git_ref` is a **pinned release tag**, not floating `main`.
- Runtime id for vllm is **`vllm`** (not `vllm-cuda`).
- Advisor scope unchanged (`ctx`, `n_gpu_layers` only).
- Containers out of scope.

---

## File structure (locked at plan start)

**Created:**

```
src/llm_cli/core/model_bindings.py
runtimes/llamacpp/_serve_flags.sh
runtimes/vllm/manifest.yaml
runtimes/vllm/params.yaml
runtimes/vllm/build.sh
runtimes/vllm/verify.sh
runtimes/vllm/serve.sh
runtimes/vllm/healthcheck.sh
runtimes/vllm/README.md
runtimes/vllm/_serve_flags.sh
tests/unit/test_model_bindings.py
tests/unit/test_llamacpp_catalog.py
tests/integration/test_cli_vllm_runtime.py
```

**Modified:**

```
src/llm_cli/core/params.py
src/llm_cli/commands/config_cmd.py
src/llm_cli/commands/runtime_cmd.py
runtimes/llamacpp/manifest.yaml
runtimes/llamacpp/params.yaml
runtimes/llamacpp/build.sh
runtimes/llamacpp/serve.sh
configs/llamacpp__*.yaml
tests/unit/test_params.py
tests/integration/test_cli_config_setup.py
tests/integration/test_cli_config_new.py
docs/add-a-runtime.md
docs/add-a-config.md
docs/wizards.md
```

---

## Phase 1 — `bind: model_path`

### Task 1: `ParamSpec.bind` + parser

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Create: `tests/unit/test_model_bindings.py` (bind parsing tests live here first)
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_params.py`:

```python
def test_parse_schema_reads_bind_model_path():
    from llm_cli.core.params import parse_schema

    specs = parse_schema(
        {
            "gguf_path": {
                "type": "path",
                "required": True,
                "bind": "model_path",
                "tier": "common",
            }
        }
    )
    assert len(specs) == 1
    assert specs[0].bind == "model_path"


def test_parse_schema_rejects_unknown_bind():
    from llm_cli.core.params import parse_schema
    import pytest

    with pytest.raises(ValueError, match="bind"):
        parse_schema({"x": {"type": "string", "bind": "other"}})
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/unit/test_params.py::test_parse_schema_reads_bind_model_path tests/unit/test_params.py::test_parse_schema_rejects_unknown_bind -v`

- [ ] **Step 3: Implement**

In `src/llm_cli/core/params.py`:

Add to `ParamSpec`:

```python
bind: str | None = None
```

After `_VALID_TIERS`, add:

```python
_VALID_BINDS = ("model_path",)


def _coerce_bind(raw: Any, key: str) -> str | None:
    if raw is None:
        return None
    token = str(raw)
    if token not in _VALID_BINDS:
        raise ValueError(
            f"param {key!r}: bind must be one of {_VALID_BINDS}; got {token!r}"
        )
    return token
```

In `parse_schema`, pass `bind=_coerce_bind(entry.get("bind"), str(key))`.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): add ParamSpec.bind for model_path binding"
```

---

### Task 2: `apply_model_bindings()` helper

**Files:**
- Create: `src/llm_cli/core/model_bindings.py`
- Modify: `tests/unit/test_model_bindings.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_model_bindings.py`:

```python
from llm_cli.core.model_bindings import apply_model_bindings, MODEL_PATH_TOKEN
from llm_cli.core.params import ParamSpec, ParamType


def _gguf_spec():
    return ParamSpec(
        key="gguf_path",
        type=ParamType.PATH,
        required=True,
        bind="model_path",
    )


def test_apply_model_bindings_injects_when_model_set():
    specs = [_gguf_spec(), ParamSpec(key="ctx", type=ParamType.INT, default=8192)]
    raw = {"ctx": "4096"}
    out = apply_model_bindings(specs, raw, model_id="my-model")
    assert out["gguf_path"] == MODEL_PATH_TOKEN
    assert out["ctx"] == "4096"


def test_apply_model_bindings_does_not_override_explicit_param():
    specs = [_gguf_spec()]
    raw = {"gguf_path": "/hardcoded/model.gguf"}
    out = apply_model_bindings(specs, raw, model_id="my-model")
    assert out["gguf_path"] == "/hardcoded/model.gguf"


def test_apply_model_bindings_skips_when_no_model():
    specs = [_gguf_spec()]
    raw = {}
    out = apply_model_bindings(specs, raw, model_id=None)
    assert "gguf_path" not in out


def test_bound_keys_for_prompt_skip():
    from llm_cli.core.model_bindings import bound_keys_to_skip

    specs = [_gguf_spec(), ParamSpec(key="ctx", type=ParamType.INT)]
    assert bound_keys_to_skip(specs, model_id="m") == {"gguf_path"}
    assert bound_keys_to_skip(specs, model_id=None) == set()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/unit/test_model_bindings.py -v`

- [ ] **Step 3: Implement**

Create `src/llm_cli/core/model_bindings.py`:

```python
"""Auto-fill serve params bound to the config's selected model."""
from __future__ import annotations

from llm_cli.core.params import ParamSpec

MODEL_PATH_TOKEN = "${model_path}"


def bound_keys_to_skip(specs: list[ParamSpec], *, model_id: str | None) -> set[str]:
    if not model_id:
        return set()
    return {s.key for s in specs if s.bind == "model_path"}


def apply_model_bindings(
    specs: list[ParamSpec],
    raw: dict[str, str],
    *,
    model_id: str | None,
) -> dict[str, str]:
    out = dict(raw)
    if not model_id:
        return out
    for spec in specs:
        if spec.bind != "model_path":
            continue
        if spec.key not in out:
            out[spec.key] = MODEL_PATH_TOKEN
    return out
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_bindings.py tests/unit/test_model_bindings.py
git commit -m "feat(config): apply_model_bindings helper for model_path params"
```

---

### Task 3: Wire config setup + config new + update tests

**Files:**
- Modify: `src/llm_cli/commands/config_cmd.py`
- Modify: `runtimes/llamacpp/params.yaml` (add `bind: model_path` on `gguf_path`)
- Modify: `tests/integration/test_cli_config_setup.py`
- Modify: `tests/integration/test_cli_config_new.py`

- [ ] **Step 1: Add bind to llamacpp params.yaml**

In `runtimes/llamacpp/params.yaml`, under `gguf_path:` add:

```yaml
  bind: model_path
```

- [ ] **Step 2: Update `do_config_new`**

At top of `do_config_new`, after resolving `rt`, before `validate_params`:

```python
from llm_cli.core.model_bindings import apply_model_bindings

merged = apply_model_bindings(rt.serve_schema, dict(params or {}), model_id=model_id)
coerced, errors = validate_params(rt.serve_schema, merged)
```

Use `merged` / `coerced` when writing `serve.params`.

- [ ] **Step 3: Update `do_config_setup` walk_specs**

Import `bound_keys_to_skip`, `MODEL_PATH_TOKEN`.

In `walk_specs`, at start of loop:

```python
skip = bound_keys_to_skip(mf.serve_schema, model_id=mid)
for spec in specs_list:
    if spec.key in skip:
        params_raw[spec.key] = MODEL_PATH_TOKEN
        continue
    ...
```

- [ ] **Step 4: Fix integration tests**

In `test_config_setup_writes_valid_yaml`, remove `"${model_path}"` from `answers` iterator (first item was gguf_path). Expected prompts start at `n_gpu_layers`.

Add new test `test_config_setup_skips_bound_path_when_model_set`:

```python
def test_config_setup_skips_bound_path_when_model_set(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    from llm_cli.core import wizards

    prompted: list[str] = []

    def capture_text(prompt, **k):
        prompted.append(prompt)
        return k.get("default", "") or ""

    monkeypatch.setattr(wizards, "text", capture_text)
    monkeypatch.setattr(wizards, "confirm", lambda *a, **k: False)
    monkeypatch.setattr(wizards, "review", lambda rows, **k: "save")

    runner.invoke(
        app,
        ["config", "setup", "--runtime", "llamacpp", "--model", "qwen-7b"],
    )
    assert "gguf_path" not in prompted

    cfg = (repo / "configs" / "llamacpp__qwen-7b__default.yaml").read_text()
    assert '${model_path}' in cfg or "${model_path}" in cfg
```

In `test_cli_config_new.py`, add test that `config new --runtime llamacpp --model X` writes `${model_path}` without `--param gguf_path`.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/unit/test_model_bindings.py tests/integration/test_cli_config_setup.py tests/integration/test_cli_config_new.py -q`

- [ ] **Step 6: Commit**

```bash
git add runtimes/llamacpp/params.yaml src/llm_cli/commands/config_cmd.py tests/integration/test_cli_config_setup.py tests/integration/test_cli_config_new.py
git commit -m "feat(config): skip bound model path prompts; auto-inject \${model_path}"
```

---

## Phase 2 — llamacpp build schema + tiered install

### Task 4: Expand llamacpp build manifest + build.sh

**Files:**
- Modify: `runtimes/llamacpp/manifest.yaml`
- Modify: `runtimes/llamacpp/build.sh`

- [ ] **Step 1: Update manifest.yaml `build:` block**

Replace `build:` with (pin `git_ref` to current stable tag at implementation time — check https://github.com/ggerganov/llama.cpp/releases):

```yaml
build:
  flavor:
    type: enum
    values: [cuda, cpu, vulkan]
    default: cuda
    tier: common
    prompt: "Which backend to build?"
  jobs:
    type: int
    default: 0
    tier: common
    prompt: "Parallel build jobs (0 = nproc)"
  git_ref:
    type: string
    default: "bXXXX"   # replace with actual release tag at implement time
    tier: common
    prompt: "llama.cpp git tag or commit to build"
  cmake_build_type:
    type: enum
    values: [Release, RelWithDebInfo, Debug]
    default: Release
    tier: advanced
  cublas:
    type: bool
    default: true
    tier: advanced
  flash_attn:
    type: bool
    default: false
    tier: advanced
  native:
    type: bool
    default: true
    tier: advanced
  cuda_architectures:
    type: string
    default: ""
    tier: advanced
    description: "Empty = cmake default; else comma-separated SM (e.g. 89;90)"
  static:
    type: bool
    default: false
    tier: advanced
  clean_build:
    type: bool
    default: false
    tier: advanced
```

- [ ] **Step 2: Update build.sh**

Key changes:

```bash
REF="${LLM_BUILD_GIT_REF:-bXXXX}"   # match manifest default
git clone --depth 1 --branch "${REF}" https://github.com/ggerganov/llama.cpp.git "${SRC}" 2>/dev/null \
  || { git clone https://github.com/ggerganov/llama.cpp.git "${SRC}" && git -C "${SRC}" checkout "${REF}"; }

if [[ "${LLM_BUILD_CLEAN_BUILD:-false}" == "true" ]]; then rm -rf "${BUILD}"; fi

CMAKE_BUILD_TYPE="${LLM_BUILD_CMAKE_BUILD_TYPE:-Release}"
CMAKE_FLAGS=(-DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE}")
# map LLM_BUILD_CUBLAS, LLM_BUILD_FLASH_ATTN, LLM_BUILD_NATIVE, LLM_BUILD_CUDA_ARCHITECTURES, LLM_BUILD_STATIC
```

Map bool env `true`/`false` to `-DGGML_CUDA=ON` etc. per flavor.

- [ ] **Step 3: Smoke**

Run: `python -m pytest tests/unit/test_registry.py -q -k llamacpp`

- [ ] **Step 4: Commit**

```bash
git add runtimes/llamacpp/manifest.yaml runtimes/llamacpp/build.sh
git commit -m "feat(llamacpp): expand tiered build params and pin git_ref"
```

---

### Task 5: Tier-aware interactive runtime install

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime.py` (or add test file)

- [ ] **Step 1: Write failing test**

```python
def test_runtime_install_interactive_reveals_advanced_build_params(monkeypatch, tmp_path):
    # seed repo with llamacpp manifest containing tier: advanced keys
    # monkeypatch wizards.confirm for advanced -> True
    # monkeypatch wizards.text to return defaults
    # mock _run_build_script
    # assert LLM_BUILD_FLASH_ATTN passed when advanced revealed
```

- [ ] **Step 2: Replace `_resolve_build_params` interactive branch**

When `yes=False`, instead of flat `typer.prompt` loop:

```python
from llm_cli.core import wizards as wiz

common = [s for s in schema if s.tier == "common"]
advanced = [s for s in schema if s.tier == "advanced"]
result = wiz.walk_tier(common + [])  # or walk common only first
# merge result.values into raw
if advanced and wiz.confirm(f"Reveal {len(advanced)} advanced build parameter(s)?", default=False):
    adv = wiz.walk_tier(advanced)
    raw.update(adv.values)
```

Extract shared `_prompt_build_specs(specs) -> dict[str, str]` if needed.

- [ ] **Step 3: Run runtime install tests**

Run: `python -m pytest tests/integration/test_cli_runtime.py -q`

- [ ] **Step 4: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/
git commit -m "feat(runtime): tier-aware interactive build param prompts"
```

---

## Phase 3 — llamacpp exhaustive serve catalog

### Task 6: Shared bash flag helper + catalog test

**Files:**
- Create: `runtimes/llamacpp/_serve_flags.sh`
- Create: `tests/unit/test_llamacpp_catalog.py`

- [ ] **Step 1: Create `_serve_flags.sh`**

```bash
# Source from serve.sh — maps LLM_LLAMACPP_* env to llama-server argv.
# Usage: append_arg_if_set ARGS VAR_NAME CLI_FLAG [is_bool]
append_arg_if_set() {
  local -n _args=$1
  local var=$2
  local flag=$3
  local val="${!var-}"
  [[ -z "$val" ]] && return 0
  _args+=("$flag" "$val")
}

append_bool_if_true() {
  local -n _args=$1
  local var=$2
  local flag=$3
  [[ "${!var:-false}" == "true" ]] && _args+=("$flag")
}
```

- [ ] **Step 2: Catalog unit test**

```python
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_llamacpp_params_keys_referenced_in_serve_sh():
    params = REPO / "runtimes/llamacpp/params.yaml"
    serve = REPO / "runtimes/llamacpp/serve.sh"
    flags = REPO / "runtimes/llamacpp/_serve_flags.sh"
    text = (params.read_text(encoding="utf-8") + serve.read_text(encoding="utf-8")
            + flags.read_text(encoding="utf-8"))
    import yaml
    schema = yaml.safe_load(params.read_text(encoding="utf-8"))
    for key in schema:
        if key == "extra_args":
            continue
        env = schema[key].get("env") or f"LLM_LLAMACPP_{key.upper()}"
        assert env in text, f"{key} env {env} not referenced in serve scripts"
```

- [ ] **Step 3: Run — expect FAIL until Task 7 completes**

- [ ] **Step 4: Commit helper + test (test may xfail until Task 7)**

```bash
git add runtimes/llamacpp/_serve_flags.sh tests/unit/test_llamacpp_catalog.py
git commit -m "test(llamacpp): assert params.yaml env vars appear in serve scripts"
```

---

### Task 7: Author exhaustive `params.yaml` (common tier)

**Files:**
- Modify: `runtimes/llamacpp/params.yaml`

- [ ] **Step 1: Add file header comment**

```yaml
# llamacpp serve params — exhaustive catalog for llama-server.
# common: shown in loco config setup without "reveal advanced".
# Regenerate/check: llama-server --help at manifest build.git_ref.
```

- [ ] **Step 2: Write common-tier entries** (minimum set — extend in Task 8):

```yaml
gguf_path:
  type: path
  required: true
  bind: model_path
  env: LLM_LLAMACPP_GGUF
  tier: common
  description: "GGUF weights file."

n_gpu_layers:
  type: int
  default: -1
  env: LLM_LLAMACPP_N_GPU_LAYERS
  tier: common
  description: "GPU layers (-1 = all)."

ctx:
  type: int
  default: 8192
  env: LLM_LLAMACPP_CTX
  tier: common
  description: "Context size in tokens."

batch_size:
  type: int
  default: 2048
  env: LLM_LLAMACPP_BATCH_SIZE
  tier: common
  description: "Logical batch size."

ubatch_size:
  type: int
  default: 512
  env: LLM_LLAMACPP_UBATCH_SIZE
  tier: common
  description: "Physical micro-batch size."

threads:
  type: int
  default: -1
  env: LLM_LLAMACPP_THREADS
  tier: common
  description: "CPU threads (-1 = auto)."

threads_batch:
  type: int
  default: -1
  env: LLM_LLAMACPP_THREADS_BATCH
  tier: common
  description: "Batch threads (-1 = auto)."

parallel:
  type: int
  default: 1
  env: LLM_LLAMACPP_PARALLEL
  tier: common
  description: "Number of server slots."

flash_attn:
  type: bool
  default: false
  env: LLM_LLAMACPP_FLASH_ATTN
  tier: common
  description: "Enable flash attention when supported."

split_mode:
  type: enum
  values: [none, layer, row]
  default: none
  env: LLM_LLAMACPP_SPLIT_MODE
  tier: common
  description: "Multi-GPU split mode."

tensor_split:
  type: string
  default: ""
  env: LLM_LLAMACPP_TENSOR_SPLIT
  tier: common
  description: "Comma-separated GPU weights for split mode."

rope_freq_base:
  type: float
  default: 0
  env: LLM_LLAMACPP_ROPE_FREQ_BASE
  tier: common
  description: "RoPE base frequency (0 = model default)."

rope_freq_scale:
  type: float
  default: 0
  env: LLM_LLAMACPP_ROPE_FREQ_SCALE
  tier: common
  description: "RoPE frequency scale (0 = model default)."

cont_batching:
  type: bool
  default: true
  env: LLM_LLAMACPP_CONT_BATCHING
  tier: common
  description: "Continuous batching."

extra_args:
  type: string
  default: ""
  env: LLM_LLAMACPP_EXTRA_ARGS
  tier: advanced
  description: "Extra flags appended verbatim (escape hatch)."
```

- [ ] **Step 3: Commit**

```bash
git add runtimes/llamacpp/params.yaml
git commit -m "feat(llamacpp): expand common-tier serve params"
```

---

### Task 8: Advanced-tier serve params + serve.sh rewrite

**Files:**
- Modify: `runtimes/llamacpp/params.yaml`
- Modify: `runtimes/llamacpp/serve.sh`

- [ ] **Step 1: Derive advanced flags from upstream**

After Task 4 pins `git_ref`, build once locally, run:

```bash
"$LLM_RUNTIMES/llamacpp/llama.cpp/build/bin/llama-server" --help
```

Add **every** documented flag not in Task 7 as `tier: advanced` entries. Group examples to implement (each gets `type`, `default`, `env: LLM_LLAMACPP_<KEY>`, `description`):

| Param key | llama-server flag | Type |
|---|---|---|
| `cache_type_k` | `--cache-type-k` | enum or string |
| `cache_type_v` | `--cache-type-v` | enum or string |
| `defrag_threshold` | `--defrag-threshold` | float |
| `no_mmap` | `--no-mmap` | bool |
| `mlock` | `--mlock` | bool |
| `no_kv_offload` | `--no-kv-offload` | bool |
| `logits_all` | `--logits-all` | bool |
| `embedding` | `--embedding` | bool |
| `reranking` | `--reranking` | bool |
| `pooling` | `--pooling` | enum |
| `metrics` | `--metrics` | bool |
| `slot_save_path` | `--slot-save-path` | path |
| `timeout` | `--timeout` | int |
| `chat_template` | `--chat-template` | string |
| `jinja` | `--jinja` | bool |
| `prop_n_predict` | `--n-predict` | int |
| _(continue until help exhaust)_ | | |

Naming rule: YAML key = flag without `--`, hyphens → underscores.

- [ ] **Step 2: Rewrite serve.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=_serve_flags.sh
source "$(dirname "${BASH_SOURCE[0]}")/_serve_flags.sh"

: "${LLM_RUNTIMES:?}"
: "${LLM_LLAMACPP_GGUF:?}"
: "${LLM_SERVE_HOST:?}"
: "${LLM_SERVE_PORT:?}"

BIN="${LLM_RUNTIMES}/llamacpp/llama.cpp/build/bin/llama-server"
[[ -x "${BIN}" ]] || { echo "error: run loco runtime install llamacpp" >&2; exit 1; }

ARGS=()
ARGS+=("${BIN}" --model "${LLM_LLAMACPP_GGUF}")
ARGS+=(--host "${LLM_SERVE_HOST}" --port "${LLM_SERVE_PORT}")

append_arg_if_set ARGS LLM_LLAMACPP_N_GPU_LAYERS --n-gpu-layers
append_arg_if_set ARGS LLM_LLAMACPP_CTX --ctx-size
append_arg_if_set ARGS LLM_LLAMACPP_BATCH_SIZE --batch-size
# ... one line per param key except extra_args and gguf_path/host/port
append_bool_if_true ARGS LLM_LLAMACPP_FLASH_ATTN --flash-attn
# ...

# shellcheck disable=SC2086
exec "${ARGS[@]}" ${LLM_LLAMACPP_EXTRA_ARGS:-}
```

Use `0` or empty checks: omit args when value is empty or `"0"` for optional floats meaning "default".

- [ ] **Step 3: Run catalog test — expect PASS**

Run: `python -m pytest tests/unit/test_llamacpp_catalog.py -v`

- [ ] **Step 4: Fix tracked configs**

Update `configs/llamacpp__*.yaml`: set `gguf_path: "${model_path}"` where `model:` is present; remove `null` gguf_path.

- [ ] **Step 5: Commit**

```bash
git add runtimes/llamacpp/params.yaml runtimes/llamacpp/serve.sh runtimes/llamacpp/_serve_flags.sh configs/
git commit -m "feat(llamacpp): exhaustive serve params and env-driven serve.sh"
```

---

## Phase 4 — vllm official runtime

### Task 9: Scaffold vllm package (manifest + build + verify)

**Files:**
- Create: `runtimes/vllm/manifest.yaml`, `build.sh`, `verify.sh`, `README.md`

- [ ] **Step 1: manifest.yaml**

```yaml
id: vllm
display_name: vLLM
kind: official
description: >
  Python vLLM OpenAI-compatible server installed via pip into a dedicated venv.
accepts_formats: [safetensors-dir]

requires:
  - id: python
    verify:
      cmd: python3 --version
      version_regex: 'Python ([\d.]+)'
      min: "3.11"
  - id: pip
    verify:
      cmd: python3 -m pip --version
      version_regex: 'pip ([\d.]+)'
      min: "23.0"
    install_hint: "python3 -m ensurepip --upgrade"

build:
  vllm_version:
    type: string
    default: "0.8.5"   # pin current stable at implement time
    tier: common
    prompt: "vLLM package version"
  pip_extra:
    type: enum
    values: [cuda, cpu, none]
    default: cuda
    tier: common
  extra_pip_packages:
    type: string
    default: ""
    tier: advanced
  force_reinstall:
    type: bool
    default: false
    tier: advanced
```

- [ ] **Step 2: build.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${LLM_RUNTIMES:?}"
ROOT="${LLM_RUNTIMES}/vllm"
VENV="${ROOT}/.venv"
python3 -m venv "${VENV}"
"${VENV}/bin/pip" install -U pip
VER="${LLM_BUILD_VLLM_VERSION:?}"
EXTRA="${LLM_BUILD_PIP_EXTRA:-cuda}"
SPEC="vllm==${VER}"
case "${EXTRA}" in
  cuda) SPEC="vllm[cuda]==${VER}" ;;
  cpu)  SPEC="vllm==${VER}" ;;
  none) SPEC="vllm==${VER}" ;;
esac
FLAGS=()
[[ "${LLM_BUILD_FORCE_REINSTALL:-false}" == "true" ]] && FLAGS+=(--force-reinstall)
"${VENV}/bin/pip" install "${FLAGS[@]}" "${SPEC}"
if [[ -n "${LLM_BUILD_EXTRA_PIP_PACKAGES:-}" ]]; then
  IFS=',' read -ra PKGS <<< "${LLM_BUILD_EXTRA_PIP_PACKAGES}"
  "${VENV}/bin/pip" install "${PKGS[@]}"
fi
```

- [ ] **Step 3: verify.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${LLM_RUNTIMES:?}"
"${LLM_RUNTIMES}/vllm/.venv/bin/vllm" --version
```

- [ ] **Step 4: chmod +x scripts; commit**

```bash
git add runtimes/vllm/
git commit -m "feat(vllm): scaffold official runtime with pip/venv build"
```

---

### Task 10: vllm params.yaml + serve.sh + healthcheck

**Files:**
- Create: `runtimes/vllm/params.yaml`, `serve.sh`, `healthcheck.sh`, `_serve_flags.sh`
- Create: `tests/unit/test_vllm_catalog.py` (mirror llamacpp catalog test)

- [ ] **Step 1: Common-tier params.yaml**

```yaml
model:
  type: path
  required: true
  bind: model_path
  env: LLM_VLLM_MODEL
  tier: common
  description: "Model path or HF id; bound to registry model when set."

dtype:
  type: string
  default: auto
  env: LLM_VLLM_DTYPE
  tier: common

max_model_len:
  type: int
  default: 0
  env: LLM_VLLM_MAX_MODEL_LEN
  tier: common
  description: "0 = model default."

gpu_memory_utilization:
  type: float
  default: 0.9
  env: LLM_VLLM_GPU_MEMORY_UTILIZATION
  tier: common

tensor_parallel_size:
  type: int
  default: 1
  env: LLM_VLLM_TENSOR_PARALLEL_SIZE
  tier: common

pipeline_parallel_size:
  type: int
  default: 1
  env: LLM_VLLM_PIPELINE_PARALLEL_SIZE
  tier: common

enforce_eager:
  type: bool
  default: false
  env: LLM_VLLM_ENFORCE_EAGER
  tier: common

swap_space:
  type: int
  default: 4
  env: LLM_VLLM_SWAP_SPACE
  tier: common

max_num_seqs:
  type: int
  default: 0
  env: LLM_VLLM_MAX_NUM_SEQS
  tier: common

extra_args:
  type: string
  default: ""
  env: LLM_VLLM_EXTRA_ARGS
  tier: advanced
```

- [ ] **Step 2: Advanced tier** — run `"${VENV}/bin/vloco serve --help"` after Task 9 install; add remaining flags (`quantization`, `enable_lora`, `trust_remote_code`, etc.) as `tier: advanced`.

- [ ] **Step 3: serve.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_serve_flags.sh"
VLLM="${LLM_RUNTIMES}/vllm/.venv/bin/vllm"
ARGS=(serve --model "${LLM_VLLM_MODEL}")
append_arg_if_set ARGS LLM_VLLM_DTYPE --dtype
append_arg_if_set ARGS LLM_VLLM_MAX_MODEL_LEN --max-model-len
# ... host/port from LLM_SERVE_HOST / LLM_SERVE_PORT
ARGS+=(--host "${LLM_SERVE_HOST}" --port "${LLM_SERVE_PORT}")
exec "${VLLM}" "${ARGS[@]}" ${LLM_VLLM_EXTRA_ARGS:-}
```

- [ ] **Step 4: healthcheck.sh** — curl `/v1/models` on host:port (reuse pattern from stub if present).

- [ ] **Step 5: Catalog test + commit**

```bash
git add runtimes/vllm/ tests/unit/test_vllm_catalog.py
git commit -m "feat(vllm): exhaustive tiered serve params and serve.sh"
```

---

### Task 11: vllm integration tests

**Files:**
- Create: `tests/integration/test_cli_vllm_runtime.py`

- [ ] **Step 1: Write tests**

```python
def test_runtime_list_includes_vllm(tmp_path, monkeypatch):
    # seed runtimes dir with vllm manifest
    result = runner.invoke(app, ["runtime", "list"])
    assert "vllm" in result.output


def test_runtime_install_vllm_mocks_pip(tmp_path, monkeypatch):
    # monkeypatch subprocess or pip in build.sh via mock run_repo_bash
    # assert .installed written


def test_config_new_vllm_injects_model_binding(tmp_path, monkeypatch):
    # seed safetensors model + vloco runtime
    # loco config new --runtime vllm --model X
    # assert serve.params.model == "${model_path}"
```

- [ ] **Step 2: Run**

Run: `python -m pytest tests/integration/test_cli_vllm_runtime.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_cli_vllm_runtime.py
git commit -m "test(vllm): integration tests for list, install, config binding"
```

---

## Phase 5 — Docs + final verification

### Task 12: Documentation

**Files:**
- Modify: `docs/add-a-runtime.md`, `docs/add-a-config.md`, `docs/wizards.md`

- [ ] **Step 1: Document `bind: model_path`** in add-a-runtime.md ParamSpec table.

- [ ] **Step 2: Document config setup skip behavior** in wizards.md.

- [ ] **Step 3: Add vllm subsection** to add-a-runtime.md (layout + pip install notes).

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs: bind model_path, llamacpp/vllm param catalogs"
```

---

### Task 13: Full suite + manual smoke checklist

- [ ] **Step 1: Run full pytest**

Run: `python -m pytest tests -q`  
Expected: all pass (existing skips OK).

- [ ] **Step 2: Manual WSL smoke** (human)

- [ ] `loco runtime install llamacpp --yes` with new defaults
- [ ] `loco config setup --runtime llamacpp --model <id>` — no gguf_path prompt
- [ ] `loco runtime install vllm --yes` — venv + pip succeed
- [ ] `loco config validate` green

- [ ] **Step 3: Commit spec/plan if not yet committed**

```bash
git add docs/superpowers/specs/2026-05-18-llamacpp-vllm-runtime-params-design.md docs/superpowers/plans/2026-05-18-llamacpp-vllm-runtime-params.md
git commit -m "docs: llamacpp/vloco runtime params spec and plan"
```

---

## Spec coverage self-review

| Spec requirement | Task |
|---|---|
| `ParamSpec.bind` | 1, 2, 3 |
| Config setup skip + inject | 3 |
| llamacpp exhaustive build | 4, 5 |
| llamacpp exhaustive serve | 6, 7, 8 |
| Tiered install prompts | 5 |
| vllm official runtime | 9, 10, 11 |
| Config migration `${model_path}` | 3, 8 |
| Docs | 12 |
| Success criteria / pytest | 13 |

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-18-llamacpp-vllm-runtime-params.md`.**

Two execution options:

1. **Subagent-driven (recommended)** — fresh subagent per task, review between tasks, fast iteration  
2. **Inline execution** — implement tasks in this session with checkpoints

Which approach do you want?
