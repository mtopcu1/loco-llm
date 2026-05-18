# 0.2 Wizards, Recommendations & Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `llm runtime setup`, `llm config setup`, `llm config new`, `llm advisor`, and the `llm setup` Y/n chain on top of a refactored runtime schema (`params.yaml` split, `kind: official | custom`). Implements the spec at `docs/superpowers/specs/2026-05-18-wizards-and-advisor.md`.

**Architecture:** Bottom-up. First, the schema refactor (`params.yaml` extracted from `manifest.yaml`, `kind:` field added) lands with the in-repo migration of `llamacpp` and `stub-runtime`. Then two standalone modules: `core/recommendations.py` (one hard-coded llamacpp branch) and `core/wizards.py` (hybrid questionary + Rich primitives with non-TTY fallback). On top of these, four new commands land: `llm advisor` (uses recommendations), `llm config new` (non-interactive generator), `llm config setup` (wizard using wizards + recommendations), `llm runtime setup` (preset + custom branches). Finally, `core/chain.py` orchestrates `llm setup`'s Y/n chain by calling the new sub-commands as Python functions (every new command exposes a `do_<verb>(...) -> str | None` helper that the chain consumes).

**Tech Stack:** Python 3.11+, Typer (CLI), Rich (output), `questionary` (new, ~2.0 for arrow-key TUI), pytest, PyYAML, stdlib `subprocess`/`socket`/`hashlib`.

**Reference spec:** `docs/superpowers/specs/2026-05-18-wizards-and-advisor.md`

**Running tests:** all commands assume the LocalLLM venv on PATH. From WSL:

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/c/Private/Projects/local-llm-scaffold
/home/$USER/llm/.cli-venv/bin/python -m pytest tests -q
```

Replace the venv path with whatever `./install.sh` produced for you (under `$LLM_DATA_ROOT/.cli-venv`).

**Locked design decisions** (resolved during brainstorming; do not revisit while implementing):

- `kind:` defaults to `"official"`. The existing `official: bool` field on `RuntimeManifest` is **derived** from `kind == "official"` (manifests may still write `official:` for backward compat; precedence: `kind:` wins if both are present).
- `params.yaml` lives at `runtimes/<id>/params.yaml`. Missing or empty file → treated as `{}` (no error).
- Pre-migration manifests with a top-level `serve:` key are rejected at load time with a clear migration hint.
- Custom-kind manifests with a `build:` key are rejected at load time.
- Recommendations module exposes `recommend(runtime_id, param_key, *, model, specs) -> Recommendation | None` and returns `None` whenever any precondition fails. Wizards then silently fall back to the schema's `default:`.
- Wizard primitives in `core/wizards.py` are the **only** module importing `questionary`. All call sites go through these wrappers so non-TTY fallback is uniform.
- Every new command exposes both a Typer entry point (for CLI use) and a plain Python helper `do_<verb>(...) -> str | None` (for in-process composition by `core/chain.py`).
- Atomic file writes everywhere: `tmp + os.replace` for `params.yaml`, `manifest.yaml`, `serve.sh`, `healthcheck.sh`, `configs/*.yaml`. The existing `install_record.write_record` already uses this pattern; the new emitters follow suit.

---

## File Structure (locked at start of plan)

**Created:**

```
src/llm_cli/core/recommendations.py                # Task 9
src/llm_cli/core/wizards.py                        # Tasks 6, 7, 8
src/llm_cli/core/chain.py                          # Task 17
src/llm_cli/commands/advisor.py                    # Tasks 10, 11, 16
runtimes/llamacpp/params.yaml                      # Task 3
runtimes/stub-runtime/params.yaml                  # Task 4 (or omitted)
tests/unit/test_recommendations.py                 # Task 9
tests/unit/test_wizards.py                         # Tasks 6, 7, 8
tests/unit/test_chain.py                           # Task 17
tests/integration/test_cli_advisor.py              # Tasks 10, 11, 16
tests/integration/test_cli_config_new.py           # Task 12
tests/integration/test_cli_config_setup.py         # Task 13
tests/integration/test_cli_runtime_setup.py        # Tasks 14, 15
tests/integration/test_cli_setup_chain.py          # Task 17
docs/wizards.md                                    # Task 18
docs/add-a-recommendation.md                       # Task 18
```

**Modified:**

```
src/llm_cli/core/params.py                         # Task 1
src/llm_cli/core/registry.py                       # Tasks 1, 2
src/llm_cli/core/install_record.py                 # Task 5
src/llm_cli/commands/runtime_cmd.py                # Tasks 14, 15, 16
src/llm_cli/commands/config_cmd.py                 # Tasks 12, 13
src/llm_cli/commands/setup.py                      # Task 17
src/llm_cli/main.py                                # Tasks 10, 12, 14, 16
runtimes/llamacpp/manifest.yaml                    # Task 3
runtimes/stub-runtime/manifest.yaml                # Task 4
requirements.txt                                   # Task 6
README.md                                          # Task 20
docs/add-a-runtime.md                              # Task 19
docs/add-a-config.md                               # Task 19
docs/runtime-lifecycle.md                          # Task 19
docs/superpowers/specs/2026-05-17-runtime-manifest-and-installs.md  # Task 20
src/llm_cli/__init__.py                            # Task 21 (version bump)
tests/unit/test_registry.py                        # Tasks 1, 2 (existing assertions need update)
tests/unit/test_install_record.py                  # Task 5 (existing assertions need update)
```

**Already correct (verify, don't touch):**

```
src/llm_cli/core/config_resolve.py                 # ${model_path} expansion already lands per the 0.1.x snapshot commit
src/llm_cli/commands/serve.py                      # .installed gate already in place and works uniformly across kinds
.gitignore                                         # state/* already listed
```

---

## Phase 1 — Schema foundation (`params.yaml` split, `kind:` field)

### Task 1: `ParamSpec` gains `tier` + `description`; `registry` loads `params.yaml`

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `src/llm_cli/core/registry.py`
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_registry.py`:

```python
def test_runtime_loads_params_yaml_with_tier_and_description(tmp_path):
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\n"
        "display_name: Demo\n"
        "accepts_formats: []\n",
        encoding="utf-8",
    )
    (rt / "params.yaml").write_text(
        "n_threads:\n"
        "  type: int\n"
        "  default: 4\n"
        "  tier: common\n"
        "  description: Number of worker threads.\n"
        "extra:\n"
        "  type: string\n"
        "  default: ''\n"
        "  tier: advanced\n"
        "  description: Pass-through flags.\n",
        encoding="utf-8",
    )

    mfs = load_runtime_manifests(tmp_path)
    assert len(mfs) == 1
    schema = mfs[0].serve_schema
    by_key = {s.key: s for s in schema}
    assert by_key["n_threads"].tier == "common"
    assert by_key["n_threads"].description == "Number of worker threads."
    assert by_key["extra"].tier == "advanced"


def test_runtime_missing_params_yaml_is_empty(tmp_path):
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\naccepts_formats: []\n", encoding="utf-8"
    )
    mfs = load_runtime_manifests(tmp_path)
    assert mfs[0].serve_schema == []


def test_runtime_manifest_with_inline_serve_is_rejected(tmp_path):
    """Pre-migration manifests must surface a clear migration error."""
    import pytest
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\naccepts_formats: []\n"
        "serve:\n  n: { type: int, default: 1 }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="serve: schema moved to params.yaml"):
        load_runtime_manifests(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_registry.py::test_runtime_loads_params_yaml_with_tier_and_description tests/unit/test_registry.py::test_runtime_missing_params_yaml_is_empty tests/unit/test_registry.py::test_runtime_manifest_with_inline_serve_is_rejected -v`

Expected: `AttributeError` on `.tier`/`.description` (ParamSpec fields missing) and `AssertionError` on the rejection test (no error raised yet).

- [ ] **Step 3: Extend `ParamSpec` and `parse_schema` to accept `tier` + `description`**

In `src/llm_cli/core/params.py`:

Add two fields to `ParamSpec` (preserve existing `frozen=True` semantics):

```python
@dataclass(frozen=True)
class ParamSpec:
    """A single typed parameter declared in a runtime manifest."""

    key: str
    type: ParamType
    default: Any = None
    required: bool = False
    prompt: str | None = None
    env: str | None = None
    values: tuple[str, ...] = field(default_factory=tuple)  # only for enum
    tier: str = "common"          # NEW: "common" | "advanced"
    description: str = ""         # NEW: one-line text for wizard + UI tooltips
```

Extend `parse_schema` to read both fields. Append at the end of the `out.append(ParamSpec(...))` call:

```python
out.append(
    ParamSpec(
        key=str(key),
        type=ptype,
        default=entry.get("default"),
        required=bool(entry.get("required", False)),
        prompt=(
            str(entry["prompt"]) if entry.get("prompt") is not None else None
        ),
        env=str(entry["env"]) if entry.get("env") is not None else None,
        values=values,
        tier=_coerce_tier(entry.get("tier", "common"), key),
        description=str(entry.get("description", "")),
    )
)
```

Add a helper near the top of the file (after `_coerce_type`):

```python
_VALID_TIERS = ("common", "advanced")


def _coerce_tier(raw: Any, key: str) -> str:
    if raw is None:
        return "common"
    token = str(raw)
    if token not in _VALID_TIERS:
        raise ValueError(
            f"param {key!r}: tier must be one of {_VALID_TIERS}; got {token!r}"
        )
    return token
```

- [ ] **Step 4: Extend `registry._to_manifest` to load `params.yaml` and reject inline `serve:`**

In `src/llm_cli/core/registry.py`, replace the body of `_to_manifest`:

```python
def _to_manifest(rec: RuntimeRecord) -> RuntimeManifest:
    data = rec.manifest
    if "serve" in data:
        raise ValueError(
            f"{rec.id}: serve: schema moved to params.yaml; "
            f"move the keys to {rec.path / 'params.yaml'}"
        )
    requires = data.get("requires") or []
    if not isinstance(requires, list):
        raise ValueError(f"{rec.id}: requires must be a list")
    raw_formats = data.get("accepts_formats", [])
    if not isinstance(raw_formats, list):
        raise ValueError(f"{rec.id}: accepts_formats must be a list of strings")
    accepts_formats = tuple(str(f) for f in raw_formats)

    params_path = rec.path / "params.yaml"
    if params_path.is_file():
        params_raw = yaml.safe_load(params_path.read_text(encoding="utf-8")) or {}
        if not isinstance(params_raw, dict):
            raise ValueError(
                f"{rec.id}: {params_path}: top-level must be a mapping"
            )
        serve_schema = parse_schema(params_raw)
    else:
        serve_schema = []

    return RuntimeManifest(
        id=rec.id,
        display_name=str(data.get("display_name", rec.id)),
        description=str(data.get("description", "")),
        official=bool(data.get("official", False)),
        build_schema=parse_schema(data.get("build") or {}),
        serve_schema=serve_schema,
        requires=[r for r in requires if isinstance(r, dict)],
        accepts_formats=accepts_formats,
        path=rec.path,
        raw=data,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_registry.py tests/unit/test_params.py -v`
Expected: all green. If the existing `test_registry.py::test_runtime_manifest_parses_schemas` test now fails because it puts `serve:` inline in the manifest, fix that test in the next step (you'll touch the same file).

- [ ] **Step 6: Fix any pre-existing test that relied on the inline `serve:` shape**

Open `tests/unit/test_registry.py`. Find the test that constructs a runtime manifest with an inline `serve:` section (search for `serve:` in the file). Move the `serve:` content into a sibling `params.yaml` file in the same `tmp_path` runtime folder. Re-run the test suite:

Run: `pytest tests/unit/test_registry.py -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/llm_cli/core/params.py src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(params): tier + description fields; load schema from params.yaml"
```

---

### Task 2: `kind: official | custom` field; reject `build:` when `custom`

**Files:**
- Modify: `src/llm_cli/core/registry.py`
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_registry.py`:

```python
def test_runtime_manifest_kind_defaults_to_official(tmp_path):
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\naccepts_formats: []\n", encoding="utf-8"
    )
    mfs = load_runtime_manifests(tmp_path)
    assert mfs[0].kind == "official"
    assert mfs[0].official is True


def test_runtime_manifest_kind_custom_is_respected(tmp_path):
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: custom\naccepts_formats: [gguf]\n",
        encoding="utf-8",
    )
    mfs = load_runtime_manifests(tmp_path)
    assert mfs[0].kind == "custom"
    assert mfs[0].official is False


def test_runtime_manifest_kind_takes_precedence_over_official_bool(tmp_path):
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: custom\nofficial: true\n"
        "accepts_formats: []\n",
        encoding="utf-8",
    )
    mfs = load_runtime_manifests(tmp_path)
    assert mfs[0].kind == "custom"
    assert mfs[0].official is False  # derived from kind, not the legacy bool


def test_custom_kind_forbids_build_section(tmp_path):
    import pytest
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: custom\naccepts_formats: []\n"
        "build:\n  flavor: { type: enum, values: [a, b], default: a }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="custom runtimes must not declare a build section"):
        load_runtime_manifests(tmp_path)


def test_unknown_kind_value_is_rejected(tmp_path):
    import pytest
    from llm_cli.core.registry import load_runtime_manifests

    rt = tmp_path / "runtimes" / "demo"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: demo\ndisplay_name: Demo\nkind: weird\naccepts_formats: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="kind must be one of"):
        load_runtime_manifests(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_registry.py -k "kind" -v`
Expected: `AttributeError` on `.kind` and `AssertionError` / no-raise on the validation tests.

- [ ] **Step 3: Add `kind` to `RuntimeManifest` and update `_to_manifest`**

In `src/llm_cli/core/registry.py`, extend the `RuntimeManifest` dataclass:

```python
@dataclass(frozen=True)
class RuntimeManifest:
    id: str
    display_name: str
    description: str
    official: bool
    kind: str                              # NEW: "official" | "custom"
    build_schema: list[ParamSpec]
    serve_schema: list[ParamSpec]
    requires: list[dict[str, Any]]
    accepts_formats: tuple[str, ...]
    path: Path
    raw: dict[str, Any]
```

Add a module-level constant and helper near `_safe_load`:

```python
_VALID_KINDS = ("official", "custom")


def _resolve_kind(data: dict[str, Any], runtime_id: str) -> str:
    if "kind" in data:
        kind = str(data["kind"])
        if kind not in _VALID_KINDS:
            raise ValueError(
                f"{runtime_id}: kind must be one of {_VALID_KINDS}; got {kind!r}"
            )
        return kind
    # Back-compat: legacy `official: true|false` field maps to kind.
    if "official" in data:
        return "official" if bool(data["official"]) else "custom"
    return "official"
```

Replace the body of `_to_manifest` to compute `kind` first and reject `build:` when custom:

```python
def _to_manifest(rec: RuntimeRecord) -> RuntimeManifest:
    data = rec.manifest
    if "serve" in data:
        raise ValueError(
            f"{rec.id}: serve: schema moved to params.yaml; "
            f"move the keys to {rec.path / 'params.yaml'}"
        )
    kind = _resolve_kind(data, rec.id)
    if kind == "custom" and "build" in data:
        raise ValueError(
            f"{rec.id}: custom runtimes must not declare a build section"
        )

    requires = data.get("requires") or []
    if not isinstance(requires, list):
        raise ValueError(f"{rec.id}: requires must be a list")
    raw_formats = data.get("accepts_formats", [])
    if not isinstance(raw_formats, list):
        raise ValueError(f"{rec.id}: accepts_formats must be a list of strings")
    accepts_formats = tuple(str(f) for f in raw_formats)

    params_path = rec.path / "params.yaml"
    if params_path.is_file():
        params_raw = yaml.safe_load(params_path.read_text(encoding="utf-8")) or {}
        if not isinstance(params_raw, dict):
            raise ValueError(
                f"{rec.id}: {params_path}: top-level must be a mapping"
            )
        serve_schema = parse_schema(params_raw)
    else:
        serve_schema = []

    return RuntimeManifest(
        id=rec.id,
        display_name=str(data.get("display_name", rec.id)),
        description=str(data.get("description", "")),
        official=(kind == "official"),
        kind=kind,
        build_schema=parse_schema(data.get("build") or {}),
        serve_schema=serve_schema,
        requires=[r for r in requires if isinstance(r, dict)],
        accepts_formats=accepts_formats,
        path=rec.path,
        raw=data,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_registry.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(registry): add kind: official|custom; reject build: when custom"
```

---

### Task 3: Migrate `runtimes/llamacpp` to split shape

**Files:**
- Modify: `runtimes/llamacpp/manifest.yaml`
- Create: `runtimes/llamacpp/params.yaml`

- [ ] **Step 1: Create `runtimes/llamacpp/params.yaml`**

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

- [ ] **Step 2: Update `runtimes/llamacpp/manifest.yaml`**

Replace the file contents with:

```yaml
id: llamacpp
display_name: llama.cpp (llama-server)
kind: official
description: >
  Builds upstream llama.cpp and serves GGUF weights via the OpenAI-compatible
  HTTP API (`llama-server`).

accepts_formats: [gguf]

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
```

(The `serve:` section is removed; the `official: true` line is replaced with `kind: official`.)

- [ ] **Step 3: Verify llamacpp loads cleanly under the new shape**

Run: `pytest tests/unit/test_registry.py -v`
Expected: all green. The new tests from Task 1/2 should still pass.

Also run any existing tests that touch the llamacpp manifest:

Run: `pytest tests -q -k "llamacpp or runtime_info or runtime_install"`
Expected: green (or, if a test asserts on the manifest YAML literal text, update it to the new shape — same task).

- [ ] **Step 4: Commit**

```bash
git add runtimes/llamacpp/manifest.yaml runtimes/llamacpp/params.yaml
git commit -m "refactor(llamacpp): split serve schema into params.yaml; declare kind: official"
```

---

### Task 4: Migrate `runtimes/stub-runtime` to split shape

**Files:**
- Modify: `runtimes/stub-runtime/manifest.yaml`
- Create: `runtimes/stub-runtime/params.yaml`

- [ ] **Step 1: Read current `runtimes/stub-runtime/manifest.yaml` and identify the serve section**

Read the file. Note which keys are currently under `serve:` (likely empty or a single placeholder).

- [ ] **Step 2: Create `runtimes/stub-runtime/params.yaml`**

Stub-runtime has no real serve params. Write the file as an explicit empty mapping so it's obvious in the repo:

```yaml
# Stub runtime exposes no serve params. Kept explicit for symmetry.
{}
```

- [ ] **Step 3: Update `runtimes/stub-runtime/manifest.yaml`**

Remove the `serve:` block (if present). Replace `official: true` (if present) with `kind: official`. Other fields untouched. Example final shape:

```yaml
id: stub-runtime
display_name: Stub runtime
kind: official
description: >
  Minimal toy server used in tests and smoke checks. Binds a TCP port and
  exits cleanly on SIGTERM. Not for real inference.

accepts_formats: []

requires: []

build: {}
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/test_registry.py tests/integration -q -k "stub"`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add runtimes/stub-runtime/manifest.yaml runtimes/stub-runtime/params.yaml
git commit -m "refactor(stub-runtime): split shape; declare kind: official"
```

---

### Task 5: `install_record` supports `kind` and null fields for custom

**Files:**
- Modify: `src/llm_cli/core/install_record.py`
- Modify: `tests/unit/test_install_record.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_install_record.py`:

```python
def test_install_record_custom_kind_round_trip(tmp_path):
    from llm_cli.core.install_record import (
        InstallRecord,
        read_record,
        write_record,
    )

    runtimes_dir = tmp_path / "runtimes"
    rec = InstallRecord(
        runtime_id="vllm-custom",
        installed_at="2026-05-18T10:00:00Z",
        build_params={},
        build_sh_sha256="",
        verify_passed=None,
        schema_hash="abc123",
        kind="custom",
    )
    write_record(runtimes_dir, rec)
    got = read_record(runtimes_dir, "vllm-custom")
    assert got == rec
    assert got.kind == "custom"
    assert got.verify_passed is None


def test_install_record_kind_defaults_to_official_when_absent(tmp_path):
    """Existing .installed files (written before kind: support) still load as official."""
    import json
    from llm_cli.core.install_record import read_record, record_path

    runtimes_dir = tmp_path / "runtimes"
    p = record_path(runtimes_dir, "legacy")
    p.parent.mkdir(parents=True)
    p.write_text(
        json.dumps({
            "runtime_id": "legacy",
            "installed_at": "2026-05-15T00:00:00Z",
            "build_params": {"flavor": "cuda"},
            "build_sh_sha256": "deadbeef",
            "verify_passed": True,
            "schema_hash": "cafe",
        }),
        encoding="utf-8",
    )
    rec = read_record(runtimes_dir, "legacy")
    assert rec is not None
    assert rec.kind == "official"  # default
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_install_record.py -v`
Expected: `TypeError: ... unexpected keyword argument 'kind'` and `AttributeError` on `.kind`.

- [ ] **Step 3: Add `kind` to `InstallRecord` and update read/write**

In `src/llm_cli/core/install_record.py`:

```python
@dataclass(frozen=True)
class InstallRecord:
    runtime_id: str
    installed_at: str
    build_params: dict[str, Any] = field(default_factory=dict)
    build_sh_sha256: str = ""
    verify_passed: bool | None = None
    schema_hash: str = ""
    kind: str = "official"          # NEW: "official" | "custom"
```

Update `read_record` to read the new field with a default:

```python
def read_record(runtimes_dir: Path, runtime_id: str) -> InstallRecord | None:
    p = record_path(runtimes_dir, runtime_id)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{p}: corrupt install record ({exc})") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: corrupt install record (top-level not object)")
    return InstallRecord(
        runtime_id=str(raw.get("runtime_id", runtime_id)),
        installed_at=str(raw.get("installed_at", "")),
        build_params=dict(raw.get("build_params") or {}),
        build_sh_sha256=str(raw.get("build_sh_sha256", "")),
        verify_passed=raw.get("verify_passed"),
        schema_hash=str(raw.get("schema_hash", "")),
        kind=str(raw.get("kind", "official")),
    )
```

`write_record` is unchanged — `asdict(rec)` already serializes the new field, and `json.dumps(..., sort_keys=True)` keeps output deterministic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_install_record.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/install_record.py tests/unit/test_install_record.py
git commit -m "feat(install-record): add kind field with official default; back-compat read"
```

---

## Phase 2 — Standalone modules

### Task 6: Add `questionary` dep + `core/wizards.py` primitives

**Files:**
- Modify: `requirements.txt`
- Create: `src/llm_cli/core/wizards.py`
- Create: `tests/unit/test_wizards.py`

- [ ] **Step 1: Add `questionary` to `requirements.txt`**

Open `requirements.txt`. Add a new line (group alphabetically with other runtime deps):

```
questionary>=2.0,<3
```

Then install it into the venv so tests can import:

Run: `/home/$USER/llm/.cli-venv/bin/pip install -r requirements.txt`
Expected: `questionary` and `prompt_toolkit` installed.

- [ ] **Step 2: Write the failing tests for the basic primitives**

```python
# tests/unit/test_wizards.py
"""Tests for the hybrid TUI primitives in core/wizards.py.

The questionary calls themselves are not exercised here — they're patched at
the `core.wizards` module surface. These tests verify the wrappers' contracts:
non-TTY fallback, default handling, type signatures.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from llm_cli.core import wizards


def test_use_plain_prompts_returns_true_when_not_a_tty(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert wizards.use_plain_prompts() is True


def test_use_plain_prompts_returns_true_when_term_is_dumb(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "dumb")
    assert wizards.use_plain_prompts() is True


def test_use_plain_prompts_returns_false_on_real_tty(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert wizards.use_plain_prompts() is False


def test_text_returns_default_when_user_hits_enter(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="8192") as ask:
        out = wizards.text("ctx", default="8192")
    assert out == "8192"
    ask.assert_called_once()


def test_select_falls_back_to_numbered_list_when_plain(monkeypatch, capsys):
    """When use_plain_prompts() is True, select() uses a numbered Rich prompt."""
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="2"):
        out = wizards.select("pick one", ["alpha", "beta", "gamma"])
    assert out == "beta"


def test_select_uses_questionary_on_tty(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: False)
    fake_q = type(
        "FakeQ", (), {"ask": staticmethod(lambda: "beta")}
    )
    with patch("questionary.select", return_value=fake_q) as q_select:
        out = wizards.select("pick one", ["alpha", "beta", "gamma"])
    assert out == "beta"
    q_select.assert_called_once()


def test_confirm_plain_yes_default(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="") as ask:
        out = wizards.confirm("ok?", default=True)
    assert out is True
    # Rich Prompt.ask was called with the default shown
    args, kwargs = ask.call_args
    assert "[Y/n]" in args[0]


def test_confirm_plain_no_input(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="n"):
        out = wizards.confirm("ok?", default=True)
    assert out is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_wizards.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_cli.core.wizards'`.

- [ ] **Step 4: Create `src/llm_cli/core/wizards.py` with the basic primitives**

```python
"""Hybrid TUI primitives.

`select` / `checkbox` / `confirm` use `questionary` (arrow-key TUI) on a real
TTY, and fall back to plain numbered-list / Rich prompts on non-TTY, dumb
terminals, or when `--quiet` is in effect.

This is the ONLY module that imports `questionary`. All wizard call sites go
through these wrappers so test seams (and degraded-terminal behavior) are
uniform.
"""
from __future__ import annotations

import os
import sys
from typing import Callable

from rich.prompt import Prompt

Choice = str  # v1: simple string choices. Extend later if labels diverge from values.


_FORCE_PLAIN = False


def force_plain(flag: bool) -> None:
    """Override TTY detection. Set by --quiet flags before calling primitives."""
    global _FORCE_PLAIN
    _FORCE_PLAIN = flag


def use_plain_prompts() -> bool:
    """Return True when the rich TUI should be skipped."""
    if _FORCE_PLAIN:
        return True
    if not sys.stdout.isatty():
        return True
    term = os.environ.get("TERM", "").lower()
    if term in ("", "dumb"):
        return True
    return False


def text(
    prompt: str,
    *,
    default: str | None = None,
    validate: Callable[[str], str | None] | None = None,
) -> str:
    """Read a free-form string. Re-prompts on validation failure."""
    while True:
        answer = Prompt.ask(prompt, default=default)
        if validate is None:
            return answer
        err = validate(answer)
        if err is None:
            return answer
        Prompt.ask.__self__  # no-op for type-checkers
        from rich.console import Console
        Console().print(f"[red]error:[/red] {err}")


def confirm(prompt: str, *, default: bool = True) -> bool:
    """Y/n confirmation. Empty answer accepts the default."""
    if use_plain_prompts():
        suffix = "[Y/n]" if default else "[y/N]"
        raw = Prompt.ask(f"{prompt} {suffix}", default="")
        token = raw.strip().lower()
        if token == "":
            return default
        if token in ("y", "yes"):
            return True
        if token in ("n", "no"):
            return False
        return default  # tolerate gibberish, fall back to default
    import questionary
    return bool(questionary.confirm(prompt, default=default).ask())


def select(
    prompt: str,
    choices: list[Choice],
    *,
    default: str | None = None,
) -> str:
    """Pick one of the choices. Arrow-key TUI on TTY, numbered list otherwise."""
    if not choices:
        raise ValueError("select() requires at least one choice")
    if use_plain_prompts():
        from rich.console import Console
        Console().print(f"\n{prompt}")
        for i, c in enumerate(choices, start=1):
            marker = " <" if c == default else ""
            Console().print(f"  [{i}] {c}{marker}")
        default_str = str(choices.index(default) + 1) if default in choices else None
        while True:
            raw = Prompt.ask(">", default=default_str)
            try:
                idx = int(raw.strip())
            except ValueError:
                continue
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
    import questionary
    return questionary.select(prompt, choices=list(choices), default=default).ask()
```

(Note: `checkbox` and the higher-level helpers come in Tasks 7-8. We're landing primitives first.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_wizards.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/llm_cli/core/wizards.py tests/unit/test_wizards.py
git commit -m "feat(wizards): add core/wizards.py primitives (text/confirm/select) + tty fallback"
```

---

### Task 7: `wizards.py` checkbox + `walk_tier` helper

**Files:**
- Modify: `src/llm_cli/core/wizards.py`
- Modify: `tests/unit/test_wizards.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_wizards.py`:

```python
def test_checkbox_plain_parses_comma_indices(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="1,3"):
        out = wizards.checkbox("pick any", ["a", "b", "c"])
    assert out == ("a", "c")


def test_checkbox_plain_accepts_empty(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    with patch("llm_cli.core.wizards.Prompt.ask", return_value=""):
        out = wizards.checkbox("pick any", ["a", "b", "c"])
    assert out == ()


def test_walk_tier_yields_common_then_offers_advanced(monkeypatch):
    """walk_tier prompts for common params, then asks before showing advanced."""
    from llm_cli.core.params import ParamSpec, ParamType

    specs = [
        ParamSpec(key="ctx", type=ParamType.INT, default=8192, tier="common",
                  description="Context window"),
        ParamSpec(key="extra", type=ParamType.STRING, default="", tier="advanced",
                  description="Pass-through"),
    ]
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    # Three prompts: ctx (common), reveal-advanced confirm, extra (advanced)
    answers = iter(["8192", "y", "--foo"])
    with patch("llm_cli.core.wizards.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        result = wizards.walk_tier(specs)
    assert result.values == {"ctx": "8192", "extra": "--foo"}
    assert result.advanced_revealed is True


def test_walk_tier_skips_advanced_when_user_declines(monkeypatch):
    from llm_cli.core.params import ParamSpec, ParamType

    specs = [
        ParamSpec(key="ctx", type=ParamType.INT, default=8192, tier="common",
                  description="Context window"),
        ParamSpec(key="extra", type=ParamType.STRING, default="", tier="advanced",
                  description="Pass-through"),
    ]
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    answers = iter(["8192", "n"])
    with patch("llm_cli.core.wizards.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        result = wizards.walk_tier(specs)
    assert result.values == {"ctx": "8192"}
    assert result.advanced_revealed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_wizards.py -v -k "checkbox or walk_tier"`
Expected: `AttributeError: module 'llm_cli.core.wizards' has no attribute 'checkbox'/'walk_tier'`.

- [ ] **Step 3: Add `checkbox` and `walk_tier` to `wizards.py`**

Append to `src/llm_cli/core/wizards.py`:

```python
from dataclasses import dataclass, field


def checkbox(
    prompt: str,
    choices: list[Choice],
    *,
    defaults: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Multi-select. Plain fallback uses comma-separated 1-based indices."""
    if use_plain_prompts():
        from rich.console import Console
        Console().print(f"\n{prompt}  (comma-separated indices, empty = none)")
        for i, c in enumerate(choices, start=1):
            marker = " [default]" if c in defaults else ""
            Console().print(f"  [{i}] {c}{marker}")
        default_str = ",".join(
            str(choices.index(d) + 1) for d in defaults if d in choices
        )
        raw = Prompt.ask(">", default=default_str)
        if not raw.strip():
            return ()
        picked: list[str] = []
        for token in raw.split(","):
            t = token.strip()
            if not t:
                continue
            try:
                idx = int(t)
            except ValueError:
                continue
            if 1 <= idx <= len(choices):
                picked.append(choices[idx - 1])
        return tuple(picked)
    import questionary
    return tuple(
        questionary.checkbox(prompt, choices=list(choices)).ask() or []
    )


@dataclass(frozen=True)
class TierWalkResult:
    values: dict[str, str] = field(default_factory=dict)
    advanced_revealed: bool = False


def walk_tier(specs: list) -> TierWalkResult:
    """Prompt all `common`-tier specs; offer to reveal `advanced` if any exist.

    Returns raw string answers (caller coerces via `params.validate_params`).
    Each prompt is rendered as:

        <key> — <description>
          suggested <value>  (<reason>)        # only if caller passes recs (future)
        <key> [<default>]:
    """
    from rich.console import Console

    console = Console()
    common = [s for s in specs if s.tier == "common"]
    advanced = [s for s in specs if s.tier == "advanced"]
    values: dict[str, str] = {}

    for spec in common:
        if spec.description:
            console.print(f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}")
        default = "" if spec.default is None else str(spec.default)
        values[spec.key] = text(spec.key, default=default or None) or default

    revealed = False
    if advanced:
        revealed = confirm(
            f"reveal {len(advanced)} advanced param(s)?", default=False
        )
        if revealed:
            for spec in advanced:
                if spec.description:
                    console.print(
                        f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}"
                    )
                default = "" if spec.default is None else str(spec.default)
                values[spec.key] = text(spec.key, default=default or None) or default

    return TierWalkResult(values=values, advanced_revealed=revealed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_wizards.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/wizards.py tests/unit/test_wizards.py
git commit -m "feat(wizards): add checkbox + walk_tier helpers with plain fallback"
```

---

### Task 8: `wizards.py` review screen helper

**Files:**
- Modify: `src/llm_cli/core/wizards.py`
- Modify: `tests/unit/test_wizards.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_wizards.py`:

```python
def test_review_save_returns_save(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    rows = [("runtime", "llamacpp"), ("port", "8080")]
    # Plain fallback: select() shows the row list with Save/Abort sentinels.
    # User picks "1" which is "[Save and write file]".
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="1"):
        action = wizards.review(rows, on_edit=lambda key: None)
    assert action == "save"


def test_review_abort_returns_abort(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    rows = [("runtime", "llamacpp")]
    # 1 = Save, 2 = the row, 3 = Abort. We pick Abort (3).
    with patch("llm_cli.core.wizards.Prompt.ask", return_value="3"):
        action = wizards.review(rows, on_edit=lambda key: None)
    assert action == "abort"


def test_review_edit_loops_until_save(monkeypatch):
    monkeypatch.setattr(wizards, "use_plain_prompts", lambda: True)
    rows = [("runtime", "llamacpp"), ("port", "8080")]
    edited: list[str] = []

    answers = iter(["2", "1"])  # pick port row -> edit; then pick Save
    with patch(
        "llm_cli.core.wizards.Prompt.ask",
        side_effect=lambda *a, **k: next(answers),
    ):
        action = wizards.review(rows, on_edit=lambda key: edited.append(key))
    assert action == "save"
    assert edited == ["runtime"]  # row index 2 → first data row → "runtime"
```

Wait — re-checking the index math: in the plain layout `[1] [Save]`, `[2] runtime`, `[3] port`, `[4] [Abort]`. So selecting "2" should fire `on_edit("runtime")`. Update the assertion accordingly.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_wizards.py -k "review" -v`
Expected: `AttributeError: module 'llm_cli.core.wizards' has no attribute 'review'`.

- [ ] **Step 3: Implement `review`**

Append to `src/llm_cli/core/wizards.py`:

```python
from typing import Callable as _Callable


def review(
    rows: list[tuple[str, str]],
    *,
    on_edit: _Callable[[str], None],
) -> str:
    """Show a review screen and loop until the user picks save or abort.

    `rows` is a list of (label, value) pairs. `on_edit(label)` is invoked when
    the user picks a row to edit; the caller is responsible for re-prompting
    that single field and updating its stored value.

    Returns "save" or "abort".
    """
    SAVE = "[Save and write file]"
    ABORT = "[Abort without saving]"
    while True:
        choices: list[str] = [SAVE]
        for label, value in rows:
            choices.append(f"{label}    {value}")
        choices.append(ABORT)
        pick = select("Review — navigate to a row to edit, or save", choices)
        if pick == SAVE:
            return "save"
        if pick == ABORT:
            return "abort"
        # Edit row: strip back to label
        label = pick.split("    ", 1)[0].strip()
        on_edit(label)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_wizards.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/wizards.py tests/unit/test_wizards.py
git commit -m "feat(wizards): add review screen helper with edit loop"
```

---

### Task 9: `core/recommendations.py` — llamacpp ctx + n_gpu_layers

**Files:**
- Create: `src/llm_cli/core/recommendations.py`
- Create: `tests/unit/test_recommendations.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_recommendations.py
"""Tests for VRAM-aware recommendations (llamacpp only in v1)."""
from __future__ import annotations

from llm_cli.core.model_registry import Artifact, HFSource, Metadata, RegistryEntry
from llm_cli.core.specs import CpuInfo, GpuInfo, SystemSpecs


def _mk_model(size_bytes: int) -> RegistryEntry:
    return RegistryEntry(
        id="m",
        format="gguf",
        source=HFSource(repo="r"),
        artifact=Artifact(primary="m.gguf", files=("m.gguf",), total_size_bytes=size_bytes),
        metadata=Metadata(),
        installed_at="",
    )


def _mk_specs(vram_gb: int) -> SystemSpecs:
    return SystemSpecs(
        cpu=CpuInfo(model="X", logical_cores=1),
        ram_gb=16,
        gpus=[GpuInfo(index=0, name="Test GPU", vram_gb=vram_gb, driver="0")],
    )


def test_recommend_returns_none_for_non_llamacpp():
    from llm_cli.core.recommendations import recommend
    out = recommend("vllm", "ctx", model=_mk_model(10 * 1024**3), specs=_mk_specs(24))
    assert out is None


def test_recommend_returns_none_when_no_gpu():
    from llm_cli.core.recommendations import recommend
    specs = SystemSpecs(cpu=CpuInfo(model="X", logical_cores=1), ram_gb=16, gpus=[])
    out = recommend("llamacpp", "ctx", model=_mk_model(10 * 1024**3), specs=specs)
    assert out is None


def test_recommend_returns_none_when_model_size_unknown():
    from llm_cli.core.recommendations import recommend
    out = recommend("llamacpp", "ctx", model=_mk_model(0), specs=_mk_specs(24))
    assert out is None


def test_recommend_ctx_when_model_fits_in_vram():
    """24 GB VRAM - 1 GB headroom - 8 GB weights = 15 GB for KV; ~7680 tokens; snap to 4096."""
    from llm_cli.core.recommendations import recommend
    out = recommend("llamacpp", "ctx", model=_mk_model(8 * 1024**3), specs=_mk_specs(24))
    assert out is not None
    # Snapped to power of 2 >= 2048; should land at 4096 or 8192 depending on exact math
    assert out.value in {"4096", "8192"}
    assert "VRAM" in out.reason


def test_recommend_ctx_conservative_when_model_exceeds_vram():
    """35 GB model on 24 GB VRAM → conservative 4096 fallback."""
    from llm_cli.core.recommendations import recommend
    out = recommend("llamacpp", "ctx", model=_mk_model(35 * 1024**3), specs=_mk_specs(24))
    assert out is not None
    assert out.value == "4096"
    assert "exceeds" in out.reason.lower() or "conservative" in out.reason.lower()


def test_recommend_n_gpu_layers_all_when_fits():
    from llm_cli.core.recommendations import recommend
    out = recommend(
        "llamacpp", "n_gpu_layers", model=_mk_model(8 * 1024**3), specs=_mk_specs(24)
    )
    assert out is not None
    assert out.value == "-1"
    assert "fits" in out.reason.lower()


def test_recommend_n_gpu_layers_partial_when_overflows():
    """24 GB VRAM, 35 GB weights, headroom 1 GB → 23/35 * 60 ≈ 39 layers."""
    from llm_cli.core.recommendations import recommend
    out = recommend(
        "llamacpp", "n_gpu_layers", model=_mk_model(35 * 1024**3), specs=_mk_specs(24)
    )
    assert out is not None
    n = int(out.value)
    assert 30 <= n <= 50


def test_recommend_returns_none_for_unknown_param_key():
    from llm_cli.core.recommendations import recommend
    out = recommend(
        "llamacpp", "totally_made_up", model=_mk_model(8 * 1024**3), specs=_mk_specs(24)
    )
    assert out is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_recommendations.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_cli.core.recommendations'`.

- [ ] **Step 3: Implement `core/recommendations.py`**

```python
"""VRAM-aware recommendations.

Single entry point `recommend(...)` returns a per-param `Recommendation` or
`None`. v1 contains one hard-coded `llamacpp` branch; the signature leaves
room for per-runtime branches as new runtimes get added.

All outputs are estimates and must be labeled as such by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass

from llm_cli.core.model_registry import RegistryEntry
from llm_cli.core.specs import SystemSpecs


@dataclass(frozen=True)
class Recommendation:
    value: str   # rendered string (matches the param's `default:` shape)
    reason: str  # one-line explanation


_HEADROOM_BYTES = 1 << 30   # 1 GB reserved for OS / CUDA
_KV_BYTES_PER_TOKEN = 2 << 20  # ~2 MB / token, architecture-blind
_LAYERS_ASSUMED = 60


def _max_gpu_vram_bytes(specs: SystemSpecs) -> int:
    if not specs.gpus:
        return 0
    return max(g.vram_gb for g in specs.gpus) * (1 << 30)


def _snap_pow2(n: int, *, minimum: int) -> int:
    if n < minimum:
        return minimum
    p = minimum
    while p * 2 <= n:
        p *= 2
    return p


def _gb_text(bytes_: int) -> str:
    return f"{bytes_ / (1 << 30):.0f} GB"


def recommend(
    runtime_id: str,
    param_key: str,
    *,
    model: RegistryEntry | None,
    specs: SystemSpecs | None,
) -> Recommendation | None:
    """Return a recommendation for (runtime, param) or None if preconditions miss."""
    if runtime_id != "llamacpp":
        return None
    if model is None or specs is None:
        return None
    weights = model.artifact.total_size_bytes
    if weights <= 0:
        return None
    total_vram = _max_gpu_vram_bytes(specs)
    if total_vram <= 0:
        return None
    free_vram = max(0, total_vram - _HEADROOM_BYTES)

    if param_key == "ctx":
        available_for_kv = max(0, free_vram - weights)
        if available_for_kv <= 0:
            return Recommendation(
                value="4096",
                reason=(
                    f"model {_gb_text(weights)} exceeds free VRAM "
                    f"{_gb_text(free_vram)}; conservative default"
                ),
            )
        suggested = _snap_pow2(available_for_kv // _KV_BYTES_PER_TOKEN, minimum=2048)
        return Recommendation(
            value=str(suggested),
            reason=(
                f"{_gb_text(total_vram)} VRAM − {_gb_text(weights)} weights "
                f"→ ~{available_for_kv // _KV_BYTES_PER_TOKEN}k KV tokens; "
                "snapped to power of 2"
            ),
        )

    if param_key == "n_gpu_layers":
        if weights <= free_vram:
            return Recommendation(
                value="-1",
                reason="model fits entirely in VRAM",
            )
        suggested = max(1, int((free_vram / weights) * _LAYERS_ASSUMED))
        return Recommendation(
            value=str(suggested),
            reason=(
                f"~{_LAYERS_ASSUMED}-layer model × "
                f"({_gb_text(free_vram)}/{_gb_text(weights)})"
            ),
        )

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_recommendations.py -v`
Expected: all green.

If a test assertion fails on a borderline (e.g., the snap_pow2 lands at 8192 instead of 4096 for the "fits in VRAM" case), inspect the actual output and tighten the test, **not** the implementation. The reason: the heuristic is the spec; the test just confirms the math doesn't crash and lands within sensible bounds.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/recommendations.py tests/unit/test_recommendations.py
git commit -m "feat(recommendations): llamacpp ctx + n_gpu_layers VRAM heuristics"
```

---

## Phase 3 — Generators (`llm advisor`, `llm config new`)

### Task 10: `llm advisor` flag form (`--runtime --model`) + `--json`

**Files:**
- Create: `src/llm_cli/commands/advisor.py`
- Create: `tests/integration/test_cli_advisor.py`
- Modify: `src/llm_cli/main.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_cli_advisor.py
"""End-to-end tests for `llm advisor`."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _patch_specs(monkeypatch):
    from llm_cli.core import specs as specs_mod
    from llm_cli.core.specs import CpuInfo, GpuInfo, SystemSpecs

    fake = SystemSpecs(
        cpu=CpuInfo(model="X", logical_cores=1),
        ram_gb=16,
        gpus=[GpuInfo(index=0, name="NVIDIA RTX 4090", vram_gb=24, driver="560")],
    )
    monkeypatch.setattr(specs_mod, "detect", lambda *a, **k: fake)


def _patch_model(monkeypatch, model_id: str, size_bytes: int):
    from llm_cli.core.model_registry import (
        Artifact,
        HFSource,
        Metadata,
        RegistryEntry,
    )
    from llm_cli.core import model_registry as mr

    entry = RegistryEntry(
        id=model_id,
        format="gguf",
        source=HFSource(repo="r"),
        artifact=Artifact(primary="m.gguf", files=("m.gguf",), total_size_bytes=size_bytes),
        metadata=Metadata(),
        installed_at="",
    )
    monkeypatch.setattr(mr, "get_entry", lambda models_dir, eid: entry if eid == model_id else None)


def test_advisor_flag_form_prints_recommendations(monkeypatch, tmp_path):
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b"]
    )
    assert result.exit_code == 0, result.output
    assert "llamacpp" in result.output
    assert "qwen-7b" in result.output
    assert "ctx" in result.output
    assert "n_gpu_layers" in result.output


def test_advisor_json_output(monkeypatch, tmp_path):
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["runtime"] == "llamacpp"
    assert payload["model"] == "qwen-7b"
    assert "ctx" in payload["recommendations"]
    assert "n_gpu_layers" in payload["recommendations"]
    assert payload["machine"]["gpus"][0]["vram_gb"] == 24


def test_advisor_requires_both_runtime_and_model(monkeypatch):
    _patch_specs(monkeypatch)
    result = runner.invoke(app, ["advisor", "--runtime", "llamacpp"])
    assert result.exit_code != 0
    assert "both --runtime and --model" in result.output.lower()


def test_advisor_errors_on_unknown_model(monkeypatch):
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "exists", 8 * 1024**3)
    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "nope"]
    )
    assert result.exit_code != 0
    assert "nope" in result.output.lower()


def test_advisor_emits_empty_recommendations_for_unsupported_runtime(monkeypatch):
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "exists", 8 * 1024**3)
    # vllm is not a real runtime in this repo, but `--runtime vllm` should error
    # at the "no runtime named" check, not the recommendations step. We expect
    # an unknown-runtime error.
    result = runner.invoke(
        app, ["advisor", "--runtime", "vllm", "--model", "exists"]
    )
    assert result.exit_code != 0
    assert "vllm" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_advisor.py -v`
Expected: `No such command 'advisor'` or similar Typer failure.

- [ ] **Step 3: Create `src/llm_cli/commands/advisor.py`**

```python
"""`llm advisor` — surface VRAM-aware recommendations.

Three invocation forms:
    llm advisor                              (interactive — Task 11)
    llm advisor <config-id>                  (positional — Task 11)
    llm advisor --runtime X --model Y        (flag — this task)

`--json` available for all forms.
"""
from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.model_registry import get_entry as _get_model
from llm_cli.core.recommendations import Recommendation, recommend
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.specs import detect

console = Console()


def _render_text(
    runtime_id: str,
    model_id: str,
    specs,
    recs: dict[str, Recommendation],
) -> None:
    console.print(
        f"[bold]Recommendations for {runtime_id} + {model_id} on this machine[/bold]"
    )
    if specs.gpus:
        g = specs.gpus[0]
        console.print(f"GPU: {g.name} ({g.vram_gb} GB)\n")
    if not recs:
        console.print(
            "No recommendations available for this combination."
        )
        return
    for key, rec in recs.items():
        console.print(f"  [bold cyan]{key}[/bold cyan]  suggested [bold green]{rec.value}[/bold green]")
        console.print(f"                [dim italic]{rec.reason}[/dim italic]\n")
    console.print(
        "Notes:\n"
        "  • Estimates based on llama.cpp's typical KV cost; actual VRAM use "
        "varies\n"
        "    with quant and prompt length.\n"
        "  • Run  llm config setup  to scaffold a config using these values.\n"
    )


def _render_json(
    runtime_id: str,
    model_id: str,
    specs,
    recs: dict[str, Recommendation],
) -> None:
    payload = {
        "runtime": runtime_id,
        "model": model_id,
        "machine": {
            "gpus": [
                {"name": g.name, "vram_gb": g.vram_gb} for g in specs.gpus
            ]
        },
        "recommendations": {
            k: {"value": r.value, "reason": r.reason} for k, r in recs.items()
        },
    }
    typer.echo(json.dumps(payload, indent=2))


def do_advisor(
    *,
    runtime_id: str,
    model_id: str,
    as_json: bool = False,
) -> int:
    """Render advice for (runtime_id, model_id). Returns exit code."""
    repo = repo_root()
    settings = resolve(load_settings())

    rt_manifest = registry.get_runtime_manifest(repo, runtime_id)
    if rt_manifest is None:
        console.print(f"[red]error:[/red] no runtime named {runtime_id!r}")
        return 1

    model = _get_model(settings.models_dir, model_id)
    if model is None:
        console.print(f"[red]error:[/red] no model named {model_id!r} in registry")
        return 1

    specs = detect()
    recs: dict[str, Recommendation] = {}
    for spec in rt_manifest.serve_schema:
        r = recommend(runtime_id, spec.key, model=model, specs=specs)
        if r is not None:
            recs[spec.key] = r

    if as_json:
        _render_json(runtime_id, model_id, specs, recs)
    else:
        _render_text(runtime_id, model_id, specs, recs)

    from llm_cli.core.lifecycle import append_history
    append_history(
        repo,
        {
            "action": "advisor",
            "runtime": runtime_id,
            "model": model_id,
            "from": "flags",  # caller can override via __from__ kwarg later
        },
    )
    return 0


def advisor(
    runtime: Optional[str] = typer.Option(
        None, "--runtime", help="Runtime id (requires --model)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Model id (requires --runtime)."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit JSON instead of formatted text."
    ),
) -> None:
    """Show VRAM-aware suggestions for a (runtime, model) pair."""
    if (runtime is None) != (model is None):
        console.print(
            "[red]error:[/red] both --runtime and --model are required when "
            "not using interactive or config-id mode"
        )
        raise typer.Exit(code=1)

    if runtime is None and model is None:
        # Interactive form lands in Task 11.
        console.print(
            "[red]error:[/red] interactive mode not yet implemented "
            "(see Task 11). Use --runtime and --model."
        )
        raise typer.Exit(code=1)

    rc = do_advisor(runtime_id=runtime, model_id=model, as_json=as_json)
    if rc != 0:
        raise typer.Exit(code=rc)
```

- [ ] **Step 4: Wire `llm advisor` into `main.py`**

Append to `src/llm_cli/main.py` near the other command registrations:

```python
from llm_cli.commands.advisor import advisor as advisor_cmd
```

Add the registration call (next to `app.command("serve", ...)`):

```python
app.command(
    "advisor",
    help="VRAM-aware recommendations for a (runtime, model) pair.",
)(advisor_cmd)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_advisor.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/commands/advisor.py src/llm_cli/main.py tests/integration/test_cli_advisor.py
git commit -m "feat(advisor): flag form (--runtime --model) with --json output"
```

---

### Task 11: `llm advisor` config-id form + interactive form

**Files:**
- Modify: `src/llm_cli/commands/advisor.py`
- Modify: `tests/integration/test_cli_advisor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_cli_advisor.py`:

```python
def test_advisor_config_id_form(monkeypatch, tmp_path):
    """Positional config id reads runtime+model from the config and advises."""
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    # Point repo_root() at a tmp_path with a single config file.
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    (cfg_dir / "llamacpp__qwen-7b__default.yaml").write_text(
        "id: llamacpp__qwen-7b__default\n"
        "runtime: llamacpp\n"
        "model: qwen-7b\n"
        "serve:\n"
        "  host: 127.0.0.1\n"
        "  port: 8080\n"
        "  params:\n"
        "    gguf_path: \"${model_path}\"\n",
        encoding="utf-8",
    )
    # Mirror runtimes/ from the real repo into tmp_path so `get_runtime_manifest` finds it.
    import shutil
    from llm_cli.core.repo import repo_root as real_repo_root
    real_repo = real_repo_root()
    shutil.copytree(real_repo / "runtimes", tmp_path / "runtimes")

    from llm_cli.core import repo as repo_mod
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    result = runner.invoke(app, ["advisor", "llamacpp__qwen-7b__default"])
    assert result.exit_code == 0, result.output
    assert "llamacpp" in result.output
    assert "qwen-7b" in result.output


def test_advisor_config_id_unknown_errors(monkeypatch, tmp_path):
    _patch_specs(monkeypatch)
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    from llm_cli.core import repo as repo_mod
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    result = runner.invoke(app, ["advisor", "no-such-config"])
    assert result.exit_code != 0
    assert "no-such-config" in result.output


def test_advisor_rejects_positional_combined_with_flags(monkeypatch):
    result = runner.invoke(
        app,
        ["advisor", "some-cfg", "--runtime", "llamacpp", "--model", "qwen-7b"],
    )
    assert result.exit_code != 0
    assert "either a config id or" in result.output.lower()


def test_advisor_interactive_picks_runtime_and_model(monkeypatch, tmp_path):
    """Interactive form uses wizards.select for runtime + model selection."""
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    # Stub registry discovery + the model registry list call so the picker has options.
    from llm_cli.core import registry
    from llm_cli.core import wizards

    # Make wizards.select return "llamacpp" then "qwen-7b".
    answers = iter(["llamacpp", "qwen-7b"])
    monkeypatch.setattr(wizards, "select", lambda prompt, choices, **k: next(answers))

    # Use the real runtimes/ from the repo.
    from llm_cli.core.repo import repo_root as real_repo_root
    import shutil
    shutil.copytree(real_repo_root() / "runtimes", tmp_path / "runtimes")
    from llm_cli.core import repo as repo_mod
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    # Patch model registry list_registry to return our one model.
    from llm_cli.core import model_registry as mr
    fake_entry = mr.RegistryEntry(
        id="qwen-7b", format="gguf", source=mr.HFSource(repo="r"),
        artifact=mr.Artifact(primary="m.gguf", files=("m.gguf",), total_size_bytes=8 * 1024**3),
        metadata=mr.Metadata(), installed_at="",
    )
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: {"qwen-7b": fake_entry})

    result = runner.invoke(app, ["advisor"])
    assert result.exit_code == 0, result.output
    assert "llamacpp" in result.output
    assert "qwen-7b" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_advisor.py -v -k "config_id or interactive or rejects_positional"`
Expected: failures because the positional arg and interactive paths aren't wired yet.

- [ ] **Step 3: Extend `advisor.py` with the positional + interactive forms**

In `src/llm_cli/commands/advisor.py`, modify the Typer signature to accept a positional arg, and dispatch:

```python
def advisor(
    config_id: Optional[str] = typer.Argument(
        None, help="Existing config id to advise against."
    ),
    runtime: Optional[str] = typer.Option(
        None, "--runtime", help="Runtime id (requires --model)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Model id (requires --runtime)."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit JSON instead of formatted text."
    ),
) -> None:
    """Show VRAM-aware suggestions for a (runtime, model) pair."""
    # Mutual exclusion: positional ⊕ flags
    if config_id is not None and (runtime is not None or model is not None):
        console.print(
            "[red]error:[/red] use either a config id or --runtime/--model, not both"
        )
        raise typer.Exit(code=1)

    # Flag form: both required
    if (runtime is None) != (model is None):
        console.print(
            "[red]error:[/red] both --runtime and --model are required when "
            "not using interactive or config-id mode"
        )
        raise typer.Exit(code=1)

    # Resolve (runtime, model) from inputs
    if config_id is not None:
        repo = repo_root()
        cfg = registry.get_config(repo, config_id)
        if cfg is None:
            console.print(f"[red]error:[/red] no config named {config_id!r}")
            raise typer.Exit(code=1)
        runtime = str(cfg.data.get("runtime", ""))
        model = cfg.data.get("model")
        if not runtime or not isinstance(model, str):
            console.print(
                f"[red]error:[/red] config {config_id!r} has no runtime/model "
                "to advise on"
            )
            raise typer.Exit(code=1)
    elif runtime is None:
        # Interactive form
        runtime, model = _interactive_pick()
        if runtime is None or model is None:
            raise typer.Exit(code=1)

    rc = do_advisor(runtime_id=runtime, model_id=model, as_json=as_json)
    if rc != 0:
        raise typer.Exit(code=rc)


def _interactive_pick() -> tuple[str | None, str | None]:
    """Interactive runtime + model picker. Returns (runtime_id, model_id) or (None, None)."""
    from llm_cli.core import wizards
    from llm_cli.core.install_record import is_installed
    from llm_cli.core.model_registry import load_registry

    repo = repo_root()
    settings = resolve(load_settings())

    runtimes = registry.load_runtime_manifests(repo)
    if not runtimes:
        console.print("[red]error:[/red] no runtimes found in runtimes/")
        return (None, None)

    choices = [
        f"{rt.id}" for rt in runtimes
    ]
    runtime_id = wizards.select("Pick a runtime", choices)

    rt_manifest = next(rt for rt in runtimes if rt.id == runtime_id)
    if not rt_manifest.accepts_formats:
        console.print(
            f"[red]error:[/red] runtime {runtime_id!r} needs no model; "
            "interactive advisor requires a runtime that consumes a model"
        )
        return (None, None)

    models = [
        m for m in load_registry(settings.models_dir).values()
        if m.format in rt_manifest.accepts_formats
    ]
    if not models:
        console.print(
            f"[red]error:[/red] no models in registry match accepts_formats "
            f"{list(rt_manifest.accepts_formats)}. Try `llm model pull <hf-url>`."
        )
        return (None, None)
    model_id = wizards.select("Pick a model", [m.id for m in models])
    return (runtime_id, model_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_advisor.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/advisor.py tests/integration/test_cli_advisor.py
git commit -m "feat(advisor): positional config-id form + interactive runtime/model picker"
```

---

### Task 12: `llm config new` non-interactive generator

**Files:**
- Modify: `src/llm_cli/commands/config_cmd.py`
- Create: `tests/integration/test_cli_config_new.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_cli_config_new.py
"""End-to-end tests for `llm config new` (non-interactive)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _seed_repo(tmp_path: Path, monkeypatch) -> Path:
    """Copy the real runtimes/ into tmp_path; mock model registry + repo_root."""
    from llm_cli.core import repo as repo_mod
    from llm_cli.core import model_registry as mr
    from llm_cli.core.repo import repo_root as real_repo_root

    shutil.copytree(real_repo_root() / "runtimes", tmp_path / "runtimes")
    (tmp_path / "configs").mkdir()
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    fake_entry = mr.RegistryEntry(
        id="qwen-7b", format="gguf", source=mr.HFSource(repo="r"),
        artifact=mr.Artifact(primary="m.gguf", files=("m.gguf",), total_size_bytes=8 * 1024**3),
        metadata=mr.Metadata(), installed_at="",
    )
    monkeypatch.setattr(
        mr, "get_entry",
        lambda models_dir, eid: fake_entry if eid == "qwen-7b" else None,
    )
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: {"qwen-7b": fake_entry})
    return tmp_path


def test_config_new_writes_valid_yaml(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config", "new",
            "--runtime", "llamacpp",
            "--model", "qwen-7b",
            "--preset", "default",
            "--param", "gguf_path=${model_path}",
            "--param", "n_gpu_layers=-1",
            "--param", "ctx=8192",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = repo / "configs" / "llamacpp__qwen-7b__default.yaml"
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "runtime: llamacpp" in text
    assert "model: qwen-7b" in text
    assert "gguf_path: ${model_path}" in text


def test_config_new_requires_runtime(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(app, ["config", "new"])
    assert result.exit_code != 0
    assert "--runtime" in result.output


def test_config_new_rejects_model_for_no_model_runtime(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config", "new",
            "--runtime", "stub-runtime",
            "--model", "qwen-7b",
        ],
    )
    assert result.exit_code != 0
    assert "stub-runtime" in result.output
    assert "model" in result.output.lower()


def test_config_new_requires_model_for_model_runtime(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app, ["config", "new", "--runtime", "llamacpp"]
    )
    assert result.exit_code != 0
    assert "model" in result.output.lower()


def test_config_new_errors_on_missing_required_param(monkeypatch, tmp_path):
    _seed_repo(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "config", "new",
            "--runtime", "llamacpp",
            "--model", "qwen-7b",
            # gguf_path is required; omit it
        ],
    )
    assert result.exit_code != 0
    assert "gguf_path" in result.output


def test_config_new_overwrite_requires_force(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    (repo / "configs" / "llamacpp__qwen-7b__default.yaml").write_text(
        "id: llamacpp__qwen-7b__default\nruntime: llamacpp\nmodel: qwen-7b\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "config", "new",
            "--runtime", "llamacpp",
            "--model", "qwen-7b",
            "--param", "gguf_path=${model_path}",
        ],
    )
    assert result.exit_code != 0
    assert "exists" in result.output.lower()

    result2 = runner.invoke(
        app,
        [
            "config", "new",
            "--runtime", "llamacpp",
            "--model", "qwen-7b",
            "--param", "gguf_path=${model_path}",
            "--force",
        ],
    )
    assert result2.exit_code == 0, result2.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_config_new.py -v`
Expected: `No such command 'new'` Typer error.

- [ ] **Step 3: Add `config new` subcommand**

In `src/llm_cli/commands/config_cmd.py`, add the imports and the new subcommand:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core.params import validate_params
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve
```

Add the helper + command at the bottom of the file:

```python
def _parse_param(token: str) -> tuple[str, str]:
    if "=" not in token:
        raise typer.BadParameter(f"--param must be key=value (got {token!r})")
    k, v = token.split("=", 1)
    k = k.strip()
    if not k:
        raise typer.BadParameter("--param key cannot be empty")
    return k, v


def do_config_new(
    *,
    runtime_id: str,
    model_id: Optional[str],
    preset: str = "default",
    port: int = 8080,
    host: str = "127.0.0.1",
    params: dict[str, str] | None = None,
    force: bool = False,
    via: str = "new",   # "new" or "setup"; surfaces in history.jsonl
) -> str:
    """Write configs/<id>.yaml. Returns the new config id."""
    repo = repo_root()
    rt = registry.get_runtime_manifest(repo, runtime_id)
    if rt is None:
        raise typer.BadParameter(f"no runtime named {runtime_id!r}")

    if rt.accepts_formats and not model_id:
        raise typer.BadParameter(
            f"runtime {runtime_id!r} declares accepts_formats="
            f"{list(rt.accepts_formats)}; --model is required"
        )
    if not rt.accepts_formats and model_id:
        raise typer.BadParameter(
            f"runtime {runtime_id!r} has empty accepts_formats; "
            f"do not pass --model"
        )

    coerced, errors = validate_params(rt.serve_schema, params or {})
    if errors:
        for e in errors:
            console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)

    cid = (
        f"{runtime_id}__{model_id}__{preset}"
        if model_id
        else f"{runtime_id}__{preset}"
    )

    out_path = repo / "configs" / f"{cid}.yaml"
    if out_path.exists() and not force:
        console.print(
            f"[red]error:[/red] {out_path} already exists; pass --force to overwrite"
        )
        raise typer.Exit(code=1)

    doc: dict[str, object] = {"id": cid, "runtime": runtime_id}
    if model_id:
        doc["model"] = model_id
    doc["serve"] = {
        "host": host,
        "port": port,
        "params": (params or {}),
    }
    doc["readiness"] = {"timeout_seconds": 600}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".yaml.tmp")
    tmp.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    tmp.replace(out_path)

    from llm_cli.core.lifecycle import append_history
    append_history(repo, {"action": "config-create", "id": cid, "via": via})

    typer.echo(cid)
    return cid


@config_app.command("new")
def config_new(
    runtime: str = typer.Option(..., "--runtime", help="Runtime id."),
    model: Optional[str] = typer.Option(None, "--model", help="Model id."),
    preset: str = typer.Option("default", "--preset", help="Preset suffix."),
    port: int = typer.Option(8080, "--port"),
    host: str = typer.Option("127.0.0.1", "--host"),
    param: list[str] = typer.Option(
        [], "--param", help="key=value, repeatable."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite if exists."),
) -> None:
    """Generate configs/<id>.yaml non-interactively."""
    params: dict[str, str] = {}
    for token in param:
        k, v = _parse_param(token)
        params[k] = v
    do_config_new(
        runtime_id=runtime,
        model_id=model,
        preset=preset,
        port=port,
        host=host,
        params=params,
        force=force,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_config_new.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/config_cmd.py tests/integration/test_cli_config_new.py
git commit -m "feat(config): add `llm config new` non-interactive generator"
```

---

## Phase 4 — Wizards (`llm config setup`, `llm runtime setup`)

### Task 13: `llm config setup` wizard

**Files:**
- Modify: `src/llm_cli/commands/config_cmd.py`
- Create: `tests/integration/test_cli_config_setup.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_cli_config_setup.py
"""End-to-end tests for `llm config setup` wizard."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _seed_repo(tmp_path: Path, monkeypatch) -> Path:
    from llm_cli.core import repo as repo_mod
    from llm_cli.core import model_registry as mr
    from llm_cli.core.repo import repo_root as real_repo_root

    shutil.copytree(real_repo_root() / "runtimes", tmp_path / "runtimes")
    (tmp_path / "configs").mkdir()
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)

    fake_entry = mr.RegistryEntry(
        id="qwen-7b", format="gguf", source=mr.HFSource(repo="r"),
        artifact=mr.Artifact(primary="m.gguf", files=("m.gguf",), total_size_bytes=8 * 1024**3),
        metadata=mr.Metadata(), installed_at="",
    )
    monkeypatch.setattr(
        mr, "get_entry",
        lambda models_dir, eid: fake_entry if eid == "qwen-7b" else None,
    )
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: {"qwen-7b": fake_entry})
    return tmp_path


def test_config_setup_writes_valid_yaml(monkeypatch, tmp_path):
    """Wizard with prefilled flags and stubbed wizards.select/text writes a valid config."""
    repo = _seed_repo(tmp_path, monkeypatch)

    from llm_cli.core import wizards
    # Sequence of answers (text() calls; select() pre-filled by flags):
    # gguf_path (default ${model_path}), n_gpu_layers (default -1), ctx (default 8192),
    # decline advanced, host, port, preset
    answers = iter([
        "${model_path}", "-1", "8192", "n", "127.0.0.1", "8080", "default",
    ])
    monkeypatch.setattr(
        wizards, "text",
        lambda prompt, **k: next(answers, k.get("default", "")),
    )
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)
    monkeypatch.setattr(wizards, "review", lambda rows, **k: "save")

    result = runner.invoke(
        app,
        [
            "config", "setup",
            "--runtime", "llamacpp",
            "--model", "qwen-7b",
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = repo / "configs" / "llamacpp__qwen-7b__default.yaml"
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "gguf_path: ${model_path}" in text


def test_config_setup_abort_writes_nothing(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    from llm_cli.core import wizards
    answers = iter([
        "${model_path}", "-1", "8192", "127.0.0.1", "8080", "default",
    ])
    monkeypatch.setattr(
        wizards, "text",
        lambda prompt, **k: next(answers, k.get("default", "")),
    )
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)
    monkeypatch.setattr(wizards, "review", lambda rows, **k: "abort")

    result = runner.invoke(
        app,
        [
            "config", "setup",
            "--runtime", "llamacpp",
            "--model", "qwen-7b",
        ],
    )
    assert result.exit_code != 0
    assert not (repo / "configs" / "llamacpp__qwen-7b__default.yaml").exists()


def test_config_setup_no_compatible_models(monkeypatch, tmp_path):
    repo = _seed_repo(tmp_path, monkeypatch)
    from llm_cli.core import model_registry as mr
    monkeypatch.setattr(mr, "load_registry", lambda models_dir: {})

    from llm_cli.core import wizards
    monkeypatch.setattr(wizards, "select", lambda *a, **k: "llamacpp")
    monkeypatch.setattr(wizards, "text", lambda *a, **k: k.get("default", ""))
    monkeypatch.setattr(wizards, "confirm", lambda *a, **k: False)

    result = runner.invoke(app, ["config", "setup"])
    assert result.exit_code != 0
    assert "llm model pull" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_config_setup.py -v`
Expected: `No such command 'setup'` for the config app.

- [ ] **Step 3: Implement `config setup`**

Append to `src/llm_cli/commands/config_cmd.py`:

```python
def _pick_runtime(repo: Path) -> str | None:
    from llm_cli.core import wizards
    runtimes = registry.load_runtime_manifests(repo)
    if not runtimes:
        console.print(
            "[red]error:[/red] no runtimes found in runtimes/. "
            "Try `llm runtime setup`."
        )
        return None
    from llm_cli.core.install_record import is_installed
    settings = resolve(load_settings())
    labels = []
    for rt in runtimes:
        installed = is_installed(settings.runtimes_dir, rt.id)
        tag = "[installed]" if installed else "[not installed]"
        labels.append(f"{rt.id}  {tag}")
    pick = wizards.select("Pick a runtime", labels)
    return pick.split()[0]


def _pick_model(repo: Path, rt) -> str | None:
    from llm_cli.core import wizards
    from llm_cli.core.model_registry import load_registry

    if not rt.accepts_formats:
        return None  # no model needed
    settings = resolve(load_settings())
    models = [
        m for m in load_registry(settings.models_dir).values()
        if m.format in rt.accepts_formats
    ]
    if not models:
        console.print(
            f"[red]error:[/red] no models in registry match accepts_formats "
            f"{list(rt.accepts_formats)}. Try `llm model pull <hf-url>`."
        )
        return None
    return wizards.select("Pick a model", [m.id for m in models])


def do_config_setup(
    *,
    runtime_id: str | None = None,
    model_id: str | None = None,
    preset: str = "default",
) -> str | None:
    """Interactive config setup. Returns the new config id or None on abort."""
    from llm_cli.core import wizards
    from llm_cli.core.model_registry import get_entry as _get_model
    from llm_cli.core.recommendations import recommend
    from llm_cli.core.specs import detect

    repo = repo_root()
    if runtime_id is None:
        runtime_id = _pick_runtime(repo)
        if runtime_id is None:
            return None

    rt = registry.get_runtime_manifest(repo, runtime_id)
    if rt is None:
        console.print(f"[red]error:[/red] no runtime named {runtime_id!r}")
        return None

    if rt.accepts_formats:
        if model_id is None:
            model_id = _pick_model(repo, rt)
            if model_id is None:
                return None
    elif model_id is not None:
        console.print(
            f"[red]error:[/red] runtime {runtime_id!r} has empty accepts_formats; "
            "do not pass --model"
        )
        return None

    settings = resolve(load_settings())
    model_entry = _get_model(settings.models_dir, model_id) if model_id else None
    specs = detect()

    # Walk param tiers with recommendations injected as the default override.
    values: dict[str, str] = {}
    common = [s for s in rt.serve_schema if s.tier == "common"]
    advanced = [s for s in rt.serve_schema if s.tier == "advanced"]
    for spec in common:
        rec = recommend(runtime_id, spec.key, model=model_entry, specs=specs)
        default = (
            rec.value if rec is not None
            else ("" if spec.default is None else str(spec.default))
        )
        if spec.description:
            console.print(
                f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}"
            )
            if rec is not None:
                console.print(
                    f"  [bold green]suggested {rec.value}[/bold green]  "
                    f"[dim italic]({rec.reason})[/dim italic]"
                )
        values[spec.key] = wizards.text(spec.key, default=default or None)

    if advanced:
        reveal = wizards.confirm(
            f"reveal {len(advanced)} advanced param(s)?", default=False
        )
        if reveal:
            for spec in advanced:
                default = "" if spec.default is None else str(spec.default)
                if spec.description:
                    console.print(
                        f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}"
                    )
                values[spec.key] = wizards.text(spec.key, default=default or None)

    host = wizards.text("host", default="127.0.0.1")
    port = wizards.text("port", default="8080")
    preset = wizards.text("preset", default=preset)

    cid = (
        f"{runtime_id}__{model_id}__{preset}"
        if model_id
        else f"{runtime_id}__{preset}"
    )

    # Review loop
    rows: list[tuple[str, str]] = [
        ("runtime", runtime_id),
        ("model", model_id or "(none)"),
        ("preset", preset),
        ("host", host),
        ("port", port),
    ]
    for k, v in values.items():
        rows.append((k, v))

    def _on_edit(key: str) -> None:
        nonlocal host, port, preset
        if key in values:
            values[key] = wizards.text(key, default=values[key])
        elif key == "host":
            host = wizards.text("host", default=host)
        elif key == "port":
            port = wizards.text("port", default=port)
        elif key == "preset":
            preset = wizards.text("preset", default=preset)

    action = wizards.review(rows, on_edit=_on_edit)
    if action == "abort":
        console.print("[yellow]aborted; no files written.[/yellow]")
        return None

    return do_config_new(
        runtime_id=runtime_id,
        model_id=model_id,
        preset=preset,
        port=int(port),
        host=host,
        params=values,
        force=True,  # wizard confirmed via review
        via="setup",
    )


@config_app.command("setup")
def config_setup(
    runtime: Optional[str] = typer.Option(None, "--runtime"),
    model: Optional[str] = typer.Option(None, "--model"),
    preset: str = typer.Option("default", "--preset"),
) -> None:
    """Interactive wizard: pick runtime → pick model → walk params → save."""
    cid = do_config_setup(runtime_id=runtime, model_id=model, preset=preset)
    if cid is None:
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_config_setup.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/config_cmd.py tests/integration/test_cli_config_setup.py
git commit -m "feat(config): `llm config setup` wizard with VRAM-aware suggestions"
```

---

### Task 14: `llm runtime setup` — preset branch

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Create: `tests/integration/test_cli_runtime_setup.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_cli_runtime_setup.py
"""End-to-end tests for `llm runtime setup`."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _seed(tmp_path: Path, monkeypatch) -> Path:
    from llm_cli.core import repo as repo_mod
    from llm_cli.core.repo import repo_root as real_repo_root

    shutil.copytree(real_repo_root() / "runtimes", tmp_path / "runtimes")
    monkeypatch.setattr(repo_mod, "repo_root", lambda: tmp_path)
    return tmp_path


def test_runtime_setup_preset_lists_official_runtimes(monkeypatch, tmp_path):
    """When 'preset' is picked, the wizard lists official runtimes from runtimes/."""
    _seed(tmp_path, monkeypatch)
    from llm_cli.core import wizards
    # 1st select: "Preset"; 2nd select: pick a runtime
    picks = iter(["Preset", "stub-runtime"])
    monkeypatch.setattr(wizards, "select", lambda prompt, choices, **k: next(picks))

    # Stub the install call so we don't actually run build.sh
    from llm_cli.commands import runtime_cmd
    monkeypatch.setattr(
        runtime_cmd, "_run_install_for_id",
        lambda runtime_id, **k: True,
    )

    result = runner.invoke(app, ["runtime", "setup"])
    assert result.exit_code == 0, result.output
    assert "stub-runtime" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_runtime_setup.py -v`
Expected: `No such command 'setup'` for `runtime`.

- [ ] **Step 3: Implement preset branch**

In `src/llm_cli/commands/runtime_cmd.py`, add at the top imports:

```python
from llm_cli.core import wizards
```

Add the helper near the bottom:

```python
def _run_install_for_id(runtime_id: str, *, flags: list[str] | None = None) -> bool:
    """Invoke the existing install flow for a runtime id. Returns True on success."""
    from llm_cli.commands.runtime_cmd import runtime_install  # local to avoid cycle
    try:
        runtime_install(
            runtime_id=runtime_id,
            param=flags or [],
            yes=False,
        )
    except typer.Exit as exc:
        return exc.exit_code == 0
    return True
```

(Adjust the exact call signature of `runtime_install` to match what already exists in this file — the goal is "delegate to the existing install Typer command function with no flags." If `runtime_install` doesn't exist by that exact name, point `_run_install_for_id` at whatever the current install command function is named.)

Then add the new subcommand:

```python
@runtime_app.command("setup")
def runtime_setup() -> None:
    """Interactive wizard: install a preset OR author a custom runtime."""
    branch = wizards.select(
        "Runtime setup",
        ["Preset — install an official runtime", "Custom — register an existing install"],
    )
    if branch.startswith("Preset"):
        _setup_preset()
    else:
        _setup_custom()


def _setup_preset() -> None:
    repo = repo_root()
    manifests = [m for m in registry.load_runtime_manifests(repo) if m.kind == "official"]
    if not manifests:
        console.print("[red]error:[/red] no official runtimes found in runtimes/")
        raise typer.Exit(code=1)
    picked_id = wizards.select(
        "Pick a preset", [m.id for m in manifests]
    )
    ok = _run_install_for_id(picked_id)
    if not ok:
        raise typer.Exit(code=1)
    typer.echo(picked_id)


def _setup_custom() -> None:
    """Custom-runtime wizard lands in Task 15."""
    console.print("[red]error:[/red] custom runtime wizard lands in Task 15.")
    raise typer.Exit(code=1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_runtime_setup.py -v -k preset`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/integration/test_cli_runtime_setup.py
git commit -m "feat(runtime): `llm runtime setup` preset branch (delegates to install)"
```

---

### Task 15: `llm runtime setup` — custom branch (full author wizard)

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime_setup.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_cli_runtime_setup.py`:

```python
def test_runtime_setup_custom_writes_all_files(monkeypatch, tmp_path):
    """Custom branch writes manifest.yaml + serve.sh + healthcheck.sh + params.yaml + .installed."""
    repo = _seed(tmp_path, monkeypatch)

    from llm_cli.core import wizards
    # Outer select: pick "Custom"
    # Inner selects: serve mode ("Template")
    # checkbox: accepts_formats picks ["safetensors-dir"]
    # text() prompts in order: id, display_name, serve invocation, requires (skip)
    text_answers = iter([
        "vllm-custom",
        "vLLM (user-installed)",
        'vllm serve "$LLM_MODEL_PATH" --host "$LLM_SERVE_HOST" --port "$LLM_SERVE_PORT" $LLM_EXTRA_ARGS',
        "",  # skip requires
    ])
    select_answers = iter(["Custom — register an existing install", "Template (we wrap in bash)"])
    monkeypatch.setattr(wizards, "select", lambda prompt, choices, **k: next(select_answers))
    monkeypatch.setattr(wizards, "checkbox", lambda prompt, choices, **k: ("safetensors-dir",))
    monkeypatch.setattr(wizards, "text", lambda prompt, **k: next(text_answers, k.get("default", "")))
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)

    # Stub settings.runtimes_dir at tmp_path/runtimes_data (separate from repo runtimes/)
    from llm_cli.core import settings as settings_mod
    real_settings = settings_mod.resolve(settings_mod.load_settings())
    new_settings = real_settings.__class__(
        data_root=tmp_path / "data",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
        repo_root=tmp_path,
    )
    monkeypatch.setattr(settings_mod, "resolve", lambda *a, **k: new_settings)

    result = runner.invoke(app, ["runtime", "setup"])
    assert result.exit_code == 0, result.output

    rt_dir = repo / "runtimes" / "vllm-custom"
    assert (rt_dir / "manifest.yaml").is_file()
    assert (rt_dir / "serve.sh").is_file()
    assert (rt_dir / "healthcheck.sh").is_file()
    assert (rt_dir / "params.yaml").is_file()

    manifest = (rt_dir / "manifest.yaml").read_text(encoding="utf-8")
    assert "kind: custom" in manifest
    assert "safetensors-dir" in manifest

    params = (rt_dir / "params.yaml").read_text(encoding="utf-8")
    assert "extra_args" in params

    installed = new_settings.runtimes_dir / "vllm-custom" / ".installed"
    assert installed.is_file()


def test_runtime_setup_custom_refuses_existing_id(monkeypatch, tmp_path):
    repo = _seed(tmp_path, monkeypatch)

    from llm_cli.core import wizards
    select_answers = iter(["Custom — register an existing install", "Template (we wrap in bash)"])
    text_answers = iter(["llamacpp"])  # already exists
    monkeypatch.setattr(wizards, "select", lambda prompt, choices, **k: next(select_answers))
    monkeypatch.setattr(wizards, "text", lambda prompt, **k: next(text_answers, ""))
    monkeypatch.setattr(wizards, "checkbox", lambda prompt, choices, **k: ("gguf",))
    monkeypatch.setattr(wizards, "confirm", lambda prompt, **k: False)

    result = runner.invoke(app, ["runtime", "setup"])
    assert result.exit_code != 0
    assert "already exists" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_runtime_setup.py -v -k custom`
Expected: failure (custom branch is the Task-15 stub from Task 14).

- [ ] **Step 3: Implement the custom branch**

Replace the `_setup_custom` stub in `src/llm_cli/commands/runtime_cmd.py`:

```python
_DEFAULT_HEALTHCHECK = """\
#!/usr/bin/env bash
set -euo pipefail
HOST="${LLM_SERVE_HOST:-127.0.0.1}"
curl -fsS -o /dev/null "http://${HOST}:${LLM_SERVE_PORT}/v1/models"
"""

_SERVE_TEMPLATE = """\
#!/usr/bin/env bash
set -euo pipefail
# Env injected: LLM_SERVE_HOST, LLM_SERVE_PORT, LLM_MODEL_PATH (if model set), LLM_EXTRA_ARGS
exec {INVOCATION}
"""

_CUSTOM_PARAMS_YAML = """\
extra_args:
  type: string
  default: ""
  env: LLM_EXTRA_ARGS
  tier: common
  description: "Pass-through flags appended to your serve command."
"""


def _setup_custom() -> None:
    repo = repo_root()
    settings = resolve(load_settings())

    rt_id = wizards.text(
        "Runtime id (slug, e.g. 'vllm-custom')",
        validate=lambda v: None if v and v.replace("-", "").replace("_", "").isalnum()
        else "id must be a slug (letters, digits, dashes, underscores)",
    )
    rt_dir = repo / "runtimes" / rt_id
    if rt_dir.exists():
        console.print(
            f"[red]error:[/red] runtime {rt_id!r} already exists at "
            f"{rt_dir}. `llm runtime uninstall {rt_id} --purge` first, or "
            "pick a different id."
        )
        raise typer.Exit(code=1)

    display_name = wizards.text("Display name", default=rt_id)

    formats = wizards.checkbox(
        "Accepts which model formats?",
        ["gguf", "safetensors-dir", "none (no model needed)"],
    )
    # Normalize "none" → empty list
    if "none (no model needed)" in formats:
        accepts_formats: list[str] = []
    else:
        accepts_formats = [f for f in formats if f != "none (no model needed)"]

    mode = wizards.select(
        "Serve command",
        ["Template (we wrap in bash)", "Editor (full control)"],
    )

    if mode.startswith("Template"):
        invocation = wizards.text(
            "Bare invocation line",
            default='your-server "$LLM_MODEL_PATH" --host "$LLM_SERVE_HOST" --port "$LLM_SERVE_PORT" $LLM_EXTRA_ARGS',
        )
        serve_sh = _SERVE_TEMPLATE.format(INVOCATION=invocation)
    else:
        import os as _os
        import subprocess as _sp
        import tempfile as _tf
        with _tf.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".sh", delete=False
        ) as f:
            f.write(_SERVE_TEMPLATE.format(INVOCATION='your-server "$LLM_MODEL_PATH" --host "$LLM_SERVE_HOST" --port "$LLM_SERVE_PORT" $LLM_EXTRA_ARGS'))
            tmp_path = f.name
        editor = _os.environ.get("EDITOR", "nano")
        rc = _sp.call([editor, tmp_path])
        if rc != 0:
            console.print("[red]error:[/red] editor exited non-zero; aborting.")
            raise typer.Exit(code=1)
        serve_sh = Path(tmp_path).read_text(encoding="utf-8")
        Path(tmp_path).unlink(missing_ok=True)

    # Optional requires entry
    requires_block = ""
    req_cmd = wizards.text(
        "Add a `requires:` check? (e.g. 'vllm --version'; empty to skip)",
        default="",
    )
    if req_cmd.strip():
        req_regex = wizards.text("version regex", default=r"([\d.]+)")
        req_min = wizards.text("minimum version (empty for none)", default="")
        req_hint = wizards.text("install hint", default="")
        requires_block = (
            "requires:\n"
            f"  - id: {req_cmd.split()[0]}\n"
            "    verify:\n"
            f"      cmd: {req_cmd}\n"
            f"      version_regex: '{req_regex}'\n"
            + (f"      min: \"{req_min}\"\n" if req_min else "")
            + f"    install_hint: \"{req_hint}\"\n"
        )

    # Compose manifest.yaml
    manifest_yaml = (
        f"id: {rt_id}\n"
        f"display_name: {display_name}\n"
        "kind: custom\n"
        f"accepts_formats: {accepts_formats}\n"
        + (requires_block if requires_block else "requires: []\n")
    )

    # Write all files atomically
    rt_dir.mkdir(parents=True, exist_ok=False)
    _atomic_write(rt_dir / "manifest.yaml", manifest_yaml)
    _atomic_write(rt_dir / "params.yaml", _CUSTOM_PARAMS_YAML)
    _atomic_write(rt_dir / "serve.sh", serve_sh, executable=True)
    _atomic_write(rt_dir / "healthcheck.sh", _DEFAULT_HEALTHCHECK, executable=True)

    # Write .installed marker
    from llm_cli.core.install_record import (
        InstallRecord,
        schema_hash,
        write_record,
    )
    import yaml as _yaml
    params_data = _yaml.safe_load(_CUSTOM_PARAMS_YAML) or {}
    rec = InstallRecord(
        runtime_id=rt_id,
        installed_at=_utc_now_iso(),
        build_params={},
        build_sh_sha256="",
        verify_passed=None,
        schema_hash=schema_hash(params_data),
        kind="custom",
    )
    write_record(settings.runtimes_dir, rec)

    append_history(
        repo, {"action": "runtime-setup", "id": rt_id, "kind": "custom"}
    )

    console.print(f"[green]wrote[/green] runtimes/{rt_id}/manifest.yaml")
    console.print(f"[green]wrote[/green] runtimes/{rt_id}/params.yaml")
    console.print(f"[green]wrote[/green] runtimes/{rt_id}/serve.sh")
    console.print(f"[green]wrote[/green] runtimes/{rt_id}/healthcheck.sh")
    console.print(
        f"[green]wrote[/green] {settings.runtimes_dir / rt_id / '.installed'}"
    )
    console.print(f"\nNext: llm config setup --runtime {rt_id}")
    typer.echo(rt_id)


def _atomic_write(path: Path, text: str, *, executable: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    if executable:
        import stat
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_runtime_setup.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/integration/test_cli_runtime_setup.py
git commit -m "feat(runtime): `llm runtime setup` custom branch authors all files + .installed"
```

---

### Task 16: Boundary errors + advisor `[c] create config` chain

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `src/llm_cli/commands/advisor.py`
- Modify: `tests/integration/test_cli_runtime_setup.py`
- Modify: `tests/integration/test_cli_advisor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_cli_runtime_setup.py`:

```python
def test_runtime_install_refuses_custom_kind(monkeypatch, tmp_path):
    """Installing a kind: custom runtime via `llm runtime install` errors."""
    repo = _seed(tmp_path, monkeypatch)
    # Author a fake custom runtime to disk
    (repo / "runtimes" / "fake-custom").mkdir(parents=True)
    (repo / "runtimes" / "fake-custom" / "manifest.yaml").write_text(
        "id: fake-custom\ndisplay_name: Fake\nkind: custom\naccepts_formats: []\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["runtime", "install", "fake-custom"])
    assert result.exit_code != 0
    assert "custom" in result.output.lower()
    assert "llm runtime setup" in result.output


def test_runtime_rebuild_refuses_custom_kind(monkeypatch, tmp_path):
    repo = _seed(tmp_path, monkeypatch)
    (repo / "runtimes" / "fake-custom").mkdir(parents=True)
    (repo / "runtimes" / "fake-custom" / "manifest.yaml").write_text(
        "id: fake-custom\ndisplay_name: Fake\nkind: custom\naccepts_formats: []\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["runtime", "rebuild", "fake-custom"])
    assert result.exit_code != 0
    assert "rebuild applies to official" in result.output.lower()
```

Append to `tests/integration/test_cli_advisor.py`:

```python
def test_advisor_offers_create_config_chain(monkeypatch, tmp_path):
    """Non-JSON advisor offers [c] create config; pressing c invokes config setup."""
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)

    invoked: list[dict] = []

    def fake_do_config_setup(**kwargs):
        invoked.append(kwargs)
        return "llamacpp__qwen-7b__default"

    from llm_cli.commands import config_cmd
    monkeypatch.setattr(config_cmd, "do_config_setup", fake_do_config_setup)

    # Advisor's bonus prompt is a wizards.confirm-equivalent. Stub it to True.
    from llm_cli.commands import advisor as advisor_mod
    monkeypatch.setattr(advisor_mod, "_offer_create_config", lambda *a, **k: True)

    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b"]
    )
    assert result.exit_code == 0, result.output
    assert invoked, "config setup was not invoked"
    assert invoked[0]["runtime_id"] == "llamacpp"
    assert invoked[0]["model_id"] == "qwen-7b"


def test_advisor_json_does_not_offer_chain(monkeypatch, tmp_path):
    """JSON mode suppresses the [c] bonus."""
    _patch_specs(monkeypatch)
    _patch_model(monkeypatch, "qwen-7b", 8 * 1024**3)
    from llm_cli.commands import advisor as advisor_mod

    called = []
    monkeypatch.setattr(advisor_mod, "_offer_create_config", lambda *a, **k: called.append(1) or True)

    result = runner.invoke(
        app, ["advisor", "--runtime", "llamacpp", "--model", "qwen-7b", "--json"]
    )
    assert result.exit_code == 0
    assert not called, "chain should not fire in --json mode"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration -k "refuses_custom or create_config or json_does_not_offer" -v`
Expected: failures (no kind-aware boundary in install/rebuild; no `_offer_create_config` helper).

- [ ] **Step 3: Add boundary checks to `runtime install` / `runtime rebuild`**

In `src/llm_cli/commands/runtime_cmd.py`, at the top of the existing `runtime_install` Typer command (and `runtime_rebuild` if separate), add:

```python
mf = registry.get_runtime_manifest(repo_root(), runtime_id)
if mf is None:
    console.print(f"[red]error:[/red] no runtime named {runtime_id!r}")
    raise typer.Exit(code=1)
if mf.kind == "custom":
    console.print(
        f"[red]error:[/red] runtime {runtime_id!r} is custom; use "
        "`llm runtime setup` to re-author. Custom runtimes have no build step."
    )
    raise typer.Exit(code=1)
```

For `runtime_rebuild`, use a different message:

```python
if mf.kind == "custom":
    console.print(
        f"[red]error:[/red] rebuild applies to official runtimes only "
        f"({runtime_id!r} is kind: custom)"
    )
    raise typer.Exit(code=1)
```

- [ ] **Step 4: Add `_offer_create_config` helper to advisor.py**

In `src/llm_cli/commands/advisor.py`, add at module level:

```python
def _offer_create_config(runtime_id: str, model_id: str) -> bool:
    """Ask the user if they want to drop into `llm config setup` now."""
    from llm_cli.core import wizards
    return wizards.confirm(
        f"create a config for {runtime_id} + {model_id} now?",
        default=False,
    )
```

In the body of the Typer `advisor` command function, after `rc = do_advisor(...)` and the exit check, but **only when** `as_json is False`:

```python
if not as_json and rc == 0:
    if _offer_create_config(runtime, model):
        from llm_cli.commands.config_cmd import do_config_setup
        do_config_setup(runtime_id=runtime, model_id=model)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_runtime_setup.py tests/integration/test_cli_advisor.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py src/llm_cli/commands/advisor.py tests/integration/test_cli_runtime_setup.py tests/integration/test_cli_advisor.py
git commit -m "feat: kind-aware install/rebuild boundaries; advisor [c] create-config chain"
```

---

## Phase 5 — Chain orchestration

### Task 17: `core/chain.py` + extend `llm setup`

**Files:**
- Create: `src/llm_cli/core/chain.py`
- Modify: `src/llm_cli/commands/setup.py`
- Create: `tests/unit/test_chain.py`
- Create: `tests/integration/test_cli_setup_chain.py`

- [ ] **Step 1: Write the failing unit tests**

```python
# tests/unit/test_chain.py
"""Unit tests for the `llm setup` Y/n chain orchestrator."""
from __future__ import annotations

from llm_cli.core import chain


def test_chain_skip_all_steps_returns_zero(monkeypatch):
    """Saying 'no' to every step exits the chain successfully."""
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: False)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "")
    rc = chain.run_setup_chain()
    assert rc == 0


def test_chain_runtime_setup_failure_aborts(monkeypatch):
    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "")

    def boom(**kwargs):
        raise RuntimeError("install failed")

    monkeypatch.setattr(chain, "_do_runtime_setup", boom)
    rc = chain.run_setup_chain()
    assert rc != 0


def test_chain_threads_ids_forward(monkeypatch):
    """ids returned by each sub-step are passed as flags to the next."""
    calls: list[dict] = []

    monkeypatch.setattr(chain, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(chain, "_prompt_text", lambda *a, **k: "https://hf/x")
    monkeypatch.setattr(chain, "_do_runtime_setup", lambda **k: "rt-x")
    monkeypatch.setattr(chain, "_do_model_pull", lambda url, **k: "model-x")

    def fake_config_setup(**kwargs):
        calls.append(kwargs)
        return "cfg-x"

    def fake_serve(cid, **kwargs):
        calls.append({"serve_id": cid})
        return 0

    monkeypatch.setattr(chain, "_do_config_setup", fake_config_setup)
    monkeypatch.setattr(chain, "_do_serve", fake_serve)
    rc = chain.run_setup_chain()
    assert rc == 0
    # config_setup got the threaded ids
    assert calls[0]["runtime_id"] == "rt-x"
    assert calls[0]["model_id"] == "model-x"
    # serve got the config id
    assert calls[1]["serve_id"] == "cfg-x"
```

- [ ] **Step 2: Write the failing integration test**

```python
# tests/integration/test_cli_setup_chain.py
"""Integration test for `llm setup` chain orchestration."""
from __future__ import annotations

from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_setup_default_skips_chain(monkeypatch):
    """`llm setup --default` writes settings and does NOT invoke the chain."""
    invoked = []
    from llm_cli.core import chain
    monkeypatch.setattr(chain, "run_setup_chain", lambda: invoked.append(1) or 0)

    result = runner.invoke(app, ["setup", "--default"])
    assert result.exit_code == 0
    assert not invoked


def test_setup_invokes_chain_on_interactive_path(monkeypatch):
    """`llm setup` (no flags) writes settings and then invokes the chain."""
    invoked = []
    from llm_cli.core import chain
    monkeypatch.setattr(chain, "run_setup_chain", lambda: invoked.append(1) or 0)
    # Auto-answer the settings prompts to defaults
    monkeypatch.setattr("typer.prompt", lambda *a, **k: k.get("default", ""))
    monkeypatch.setattr("typer.confirm", lambda *a, **k: True)

    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert invoked == [1]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_chain.py tests/integration/test_cli_setup_chain.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_cli.core.chain'`.

- [ ] **Step 4: Implement `core/chain.py`**

```python
"""`llm setup` chain orchestration.

Walks the user through the four post-settings steps as Y/n prompts. Each
"no" skips that step and proceeds to the next. Each "yes" delegates to the
matching sub-command's `do_<verb>(...)` helper (in-process call). Failures
in an explicit-Y step abort the chain with non-zero exit.
"""
from __future__ import annotations

from typing import Callable

from rich.console import Console

console = Console()


# Indirection so tests can patch these by name without importing each command.
def _confirm(prompt: str, *, default: bool = True) -> bool:
    from llm_cli.core import wizards
    return wizards.confirm(prompt, default=default)


def _prompt_text(prompt: str, *, default: str = "") -> str:
    from llm_cli.core import wizards
    return wizards.text(prompt, default=default or None)


def _do_runtime_setup() -> str | None:
    from llm_cli.commands.runtime_cmd import runtime_setup as _rt_setup
    # runtime_setup is a Typer callback; calling it directly raises typer.Exit on failure.
    try:
        _rt_setup()
    except SystemExit as e:
        if int(e.code or 0) != 0:
            raise RuntimeError("runtime setup failed")
    # We rely on runtime_setup's typer.echo(rt_id) at the end for downstream consumers;
    # but for in-process we expose a parallel helper.
    from llm_cli.commands.runtime_cmd import _last_setup_id
    return _last_setup_id()


def _do_model_pull(url: str) -> str | None:
    from llm_cli.commands.model_cmd import do_model_pull
    return do_model_pull(url)


def _do_config_setup(*, runtime_id: str | None, model_id: str | None) -> str | None:
    from llm_cli.commands.config_cmd import do_config_setup
    return do_config_setup(runtime_id=runtime_id, model_id=model_id)


def _do_serve(config_id: str) -> int:
    from llm_cli.commands.serve import serve as _serve
    try:
        _serve(config_id=config_id, foreground=False, systemd=False)
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def run_setup_chain() -> int:
    """Run the four-step Y/n chain. Returns process exit code."""
    from llm_cli.core.lifecycle import append_history
    from llm_cli.core.repo import repo_root as _repo_root

    runtime_id: str | None = None
    model_id: str | None = None
    config_id: str | None = None
    steps_run: list[str] = []

    if _confirm("Install a runtime now?", default=True):
        console.print()
        try:
            runtime_id = _do_runtime_setup()
            if runtime_id:
                steps_run.append("runtime")
        except RuntimeError as e:
            console.print(f"[red]error:[/red] {e}")
            return 1

    url = _prompt_text(
        "Hugging Face URL (or empty / 'n' to skip)", default=""
    )
    if url.strip() and url.strip().lower() != "n":
        try:
            model_id = _do_model_pull(url.strip())
            if model_id:
                steps_run.append("model")
        except RuntimeError as e:
            console.print(f"[red]error:[/red] {e}")
            return 1

    if _confirm("Create a config now?", default=True):
        try:
            config_id = _do_config_setup(runtime_id=runtime_id, model_id=model_id)
            if config_id:
                steps_run.append("config")
        except RuntimeError as e:
            console.print(f"[red]error:[/red] {e}")
            return 1

    served = False
    if config_id and _confirm("Start serving this config?", default=True):
        rc = _do_serve(config_id)
        if rc != 0:
            append_history(
                _repo_root(),
                {"action": "setup-chain", "steps": steps_run, "outcome": "serve-failed"},
            )
            return rc
        served = True
        steps_run.append("serve")
        console.print(
            "\n[green]Setup complete.[/green] Use  llm status  to see what's running."
        )
    else:
        console.print(
            f"\n[green]Setup complete.[/green] "
            + (f"Next: llm serve {config_id}" if config_id else "")
        )

    append_history(
        _repo_root(),
        {"action": "setup-chain", "steps": steps_run, "outcome": "ok"},
    )
    return 0
```

- [ ] **Step 5: Add the `_last_setup_id` helper to `runtime_cmd.py`**

In `src/llm_cli/commands/runtime_cmd.py`, add a module-level variable and helper:

```python
_LAST_SETUP_ID: str | None = None


def _last_setup_id() -> str | None:
    return _LAST_SETUP_ID
```

In `runtime_setup()` (the Typer command), at every place that produces a runtime id (preset and custom both), set `globals()['_LAST_SETUP_ID']`:

In `_setup_preset` after `_run_install_for_id(picked_id)` success:
```python
global _LAST_SETUP_ID
_LAST_SETUP_ID = picked_id
```

In `_setup_custom` after the write succeeds:
```python
global _LAST_SETUP_ID
_LAST_SETUP_ID = rt_id
```

- [ ] **Step 6: Add `do_model_pull` helper to `model_cmd.py`**

In `src/llm_cli/commands/model_cmd.py`, wrap the existing `model_pull` body in a helper function `do_model_pull(url: str) -> str` that returns the model id (the existing command function should now just be a thin Typer wrapper that calls `do_model_pull` and prints the id). Look at the current `model_pull` implementation; lift the side-effect logic into `do_model_pull`, keep the Typer signature, and have the Typer command call the helper.

- [ ] **Step 7: Wire `llm setup` to invoke the chain unless `--default`**

Modify `src/llm_cli/commands/setup.py`. Replace the bottom of the `setup` function (the "Recommended next steps" panel) with:

```python
    console.print(f"[green]data_root[/green]: {resolved.data_root}")
    console.print(f"[green]runtimes_dir[/green]: {resolved.runtimes_dir}")
    console.print(f"[green]models_dir[/green]: {resolved.models_dir}")
    console.print(f"[green]cache_dir[/green]: {resolved.cache_dir}")
    console.print(f"[green]repo_root[/green]: {resolved.repo_root}")

    if default:
        # Keep today's non-interactive behavior: print the fixed hint and exit.
        console.print()
        console.print("[bold]Recommended next steps:[/bold]")
        console.print("  1. llm doctor                  # verify cross-cutting prereqs")
        console.print("  2. llm runtime setup           # install or register a runtime")
        console.print("  3. llm model pull <hf-url>     # download a model")
        console.print("  4. llm config setup            # scaffold a config")
        console.print("  5. llm serve <config-id>       # start a server")
        return

    console.print()
    from llm_cli.core.chain import run_setup_chain
    rc = run_setup_chain()
    if rc != 0:
        raise typer.Exit(code=rc)
```

- [ ] **Step 8: Run all chain tests**

Run: `pytest tests/unit/test_chain.py tests/integration/test_cli_setup_chain.py -v`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add src/llm_cli/core/chain.py src/llm_cli/commands/setup.py src/llm_cli/commands/runtime_cmd.py src/llm_cli/commands/model_cmd.py tests/unit/test_chain.py tests/integration/test_cli_setup_chain.py
git commit -m "feat(setup): Y/n chain orchestration with id threading"
```

---

## Phase 6 — Documentation & release

### Task 18: New docs — `wizards.md` + `add-a-recommendation.md`

**Files:**
- Create: `docs/wizards.md`
- Create: `docs/add-a-recommendation.md`

- [ ] **Step 1: Write `docs/wizards.md`**

```markdown
# Wizards & advisor

The 0.2 release adds four new commands on top of the existing one-shots.
Each wizard has a flag-form sibling so scripting still works.

## When to use which

| Goal | Wizard | One-shot |
|---|---|---|
| First-time setup, end-to-end | `llm setup` | `llm setup --default` |
| Install or register a runtime | `llm runtime setup` | `llm runtime install <id>` |
| Scaffold a launch config | `llm config setup` | `llm config new --runtime X --model Y --param k=v` |
| See VRAM-aware suggestions | `llm advisor` | `llm advisor --runtime X --model Y --json` |

## `llm setup` — Y/n chain orchestrator

`llm setup` writes machine settings (data root, dirs), then offers four
Y/n steps: install a runtime, pull a model, create a config, start serving.
Each "no" skips that step; an explicit "yes" that fails aborts the chain.

Pass `--default` to skip both the interactive settings prompts and the chain.

## `llm runtime setup`

Two branches:

- **Preset** — lists official runtimes (those declared `kind: official` in
  their `manifest.yaml`) and delegates to `llm runtime install <id>` for the
  picked one. Same interactive build-param prompts as today.
- **Custom** — authors a new runtime in `runtimes/<id>/` from a single
  `serve.sh` invocation. No build step, no `verify.sh`. The CLI auto-generates
  a default `healthcheck.sh` (an OpenAI-compatible `/v1/models` curl).

A `kind: custom` runtime is committed to the repo just like an official one;
the distinguisher is the `kind:` field, not folder layout.

## `llm config setup`

Walks runtime → model (filtered by `accepts_formats`) → params → save.
Common-tier params are walked first; advanced are hidden behind a confirm.
Recommendations from `llm advisor` (currently llamacpp only) are inlined
next to relevant prompts as `suggested NNN (reason)`.

The non-interactive sibling is `llm config new`. Both share the same code
path; the wizard just collects the same flag values via prompts.

## `llm advisor`

VRAM-aware recommendations from `llm specs` + the model's on-disk size.

Three forms:

```text
llm advisor                                # interactive: pick runtime → pick model
llm advisor <config-id>                    # advise against an existing config
llm advisor --runtime X --model Y          # non-interactive
```

`--json` available for any form. All outputs are estimates and labeled as
such.

After the text-form output, a one-shot `[c] create a config with these
values` prompt drops you into `llm config setup` with the runtime, model,
and suggested values pre-filled. `--json` suppresses this prompt.

## TUI behavior

The wizards use `questionary` for arrow-key selection on a real TTY, and
fall back to plain numbered prompts on non-TTY (CI, pipes, dumb terminals)
or when `--quiet` is passed.

## See also

- Spec: `docs/superpowers/specs/2026-05-18-wizards-and-advisor.md`
- Custom runtime authoring: `docs/add-a-runtime.md`
- Adding more recommendations: `docs/add-a-recommendation.md`
```

- [ ] **Step 2: Write `docs/add-a-recommendation.md`**

```markdown
# Add a per-runtime recommendation

`llm advisor` and `llm config setup` use `src/llm_cli/core/recommendations.py`
to compute VRAM-aware suggestions per param. v1 ships with one hard-coded
`llamacpp` branch for `ctx` and `n_gpu_layers`.

To add suggestions for a new runtime, extend the `recommend()` function with
a new branch. Return `None` if any precondition isn't met (no GPU, no model
size, unsupported param key); the caller falls back silently to the
schema's `default:`.

## Skeleton

```python
def recommend(runtime_id, param_key, *, model, specs):
    if runtime_id == "llamacpp":
        return _llamacpp(param_key, model=model, specs=specs)
    if runtime_id == "vllm":
        return _vllm(param_key, model=model, specs=specs)
    return None


def _vllm(param_key, *, model, specs):
    if model is None or specs is None or not specs.gpus:
        return None
    if param_key == "gpu-memory-utilization":
        # ... your math here ...
        return Recommendation(value="0.9", reason="leave 10% headroom for KV cache")
    return None
```

## Always label as estimate

Every `Recommendation.reason` should make it clear the value is approximate.
The wizard renders it as `[estimate <value>: <reason>]`; users override
freely. Wrong recommendations are worse than no recommendations — return
`None` when in doubt.

## Tests

Add unit tests in `tests/unit/test_recommendations.py` covering:

- The new branch returns expected values for representative `(vram_gb,
  weights_gb)` pairs.
- It returns `None` when preconditions fail.
- It returns `None` for unknown param keys.
```

- [ ] **Step 3: Commit**

```bash
git add docs/wizards.md docs/add-a-recommendation.md
git commit -m "docs: add wizards.md and add-a-recommendation.md"
```

---

### Task 19: Rewrite `add-a-runtime.md`; update `add-a-config.md` + `runtime-lifecycle.md`

**Files:**
- Modify: `docs/add-a-runtime.md`
- Modify: `docs/add-a-config.md`
- Modify: `docs/runtime-lifecycle.md`

- [ ] **Step 1: Read the current files**

Read each of the three files in turn to understand the current structure. Each follows the template **prerequisites → steps → verification → common pitfalls**.

- [ ] **Step 2: Rewrite `docs/add-a-runtime.md`**

The new structure should cover both branches:

**Preset (official)** — when you want `llm` to build a runtime from source
1. Drop a `runtimes/<id>/manifest.yaml` with `kind: official`, `accepts_formats:`, optional `requires:`, and a `build:` schema.
2. Drop a `runtimes/<id>/params.yaml` with your serve-time knobs (each entry needs `type:` and optionally `default`, `required`, `env`, `tier`, `description`).
3. Drop `runtimes/<id>/build.sh`, `runtimes/<id>/serve.sh`, `runtimes/<id>/healthcheck.sh`, optionally `runtimes/<id>/verify.sh`.
4. `llm runtime install <id>` builds and verifies.

**Custom** — when you already have the server installed and just want lifecycle management
1. `llm runtime setup`, pick "Custom".
2. Wizard prompts for id, display name, accepted formats, serve command (template or `$EDITOR`), optional `requires:` check.
3. Wizard writes `manifest.yaml` (with `kind: custom`), `params.yaml` (just `extra_args`), `serve.sh`, default `healthcheck.sh`, and `.installed` immediately.
4. `llm serve <config-id>` works right away.

**Env contract** — list LLM_SERVE_HOST, LLM_SERVE_PORT, LLM_MODEL_PATH, LLM_MODEL_ID, plus `params.yaml`-declared `env:` names.

**Pitfalls** — `kind: custom` rejects any `build:` section; `params.yaml` missing is treated as empty; the `${model_path}` template only resolves when the config sets `model:`.

Replace the existing file with the new content (keep the same heading levels and table-style format used elsewhere in `docs/`).

- [ ] **Step 3: Update `docs/add-a-config.md`**

Reorder the content: lead with `llm config setup` (the wizard), then document `llm config new` for scripting, then show the hand-authoring shape last as the "minimal yaml" reference. Mention the `${model_path}` template explicitly. Reference `accepts_formats` compatibility.

- [ ] **Step 4: Update `docs/runtime-lifecycle.md`**

Add a section explaining `kind: custom` semantics:
- No `build.sh` or `verify.sh`.
- `.installed` written immediately at end of `llm runtime setup`.
- `llm runtime install` and `llm runtime rebuild` refuse to act on custom runtimes.
- Drift indicators based on `build_sh_sha256` always skip custom runtimes.

- [ ] **Step 5: Commit**

```bash
git add docs/add-a-runtime.md docs/add-a-config.md docs/runtime-lifecycle.md
git commit -m "docs: rewrite add-a-runtime; update add-a-config + runtime-lifecycle for kind: custom"
```

---

### Task 20: Update `README.md` + cross-ref note on old spec

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-17-runtime-manifest-and-installs.md`

- [ ] **Step 1: Update Getting Started in `README.md`**

Replace the current "5. Install a runtime and model, validate config, serve" block with the chain-led flow:

```markdown
## Getting started (first time)

Inside WSL2:

```bash
# 1. Verify external prerequisites
cat requirements.md
# (or after install:) llm doctor

# 2. Install the CLI into a venv
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # if not already

# 3. Run the interactive setup (settings + Y/n chain into runtime / model / config / serve)
llm setup
```

For an existing setup, the granular commands still work as before:

```bash
llm runtime setup       # interactive picker (preset or custom)
llm runtime install llamacpp --yes      # non-interactive preset install
llm model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
llm config setup        # interactive
llm config new --runtime llamacpp --model qwen2-7b --param gguf_path='${model_path}'
llm serve llamacpp__qwen2-7b__default
```
```

- [ ] **Step 2: Add the `llm advisor` and `llm runtime setup` / `llm config setup` / `llm config new` rows to the CLI commands table in `README.md`**

Find the existing table (search for `| Command | Purpose |`). Add four new rows:

```markdown
| `llm runtime setup` | Interactive wizard. Picks preset (delegates to `llm runtime install`) or custom (authors a no-build runtime with bring-your-own `serve.sh`). |
| `llm config setup` | Interactive wizard. Picks runtime → model → walks params → saves config. |
| `llm config new --runtime X --model Y --param k=v` | Non-interactive sibling of `llm config setup`. |
| `llm advisor [--runtime X --model Y \| <config-id>]` | VRAM-aware suggestions for `ctx` and `n_gpu_layers` (llamacpp only in 0.2). `--json` for scripting. |
```

- [ ] **Step 3: Add cross-reference note to the prior runtime-manifest spec**

Open `docs/superpowers/specs/2026-05-17-runtime-manifest-and-installs.md`. Near the top (after the existing _Status:_ line), add:

```markdown
> **Updated 2026-05-18:** the `serve:` schema moves to a sibling `params.yaml`
> and a `kind: official | custom` field is added — see
> [`2026-05-18-wizards-and-advisor.md`](2026-05-18-wizards-and-advisor.md).
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-05-17-runtime-manifest-and-installs.md
git commit -m "docs: README leads with `llm setup` chain; cross-ref the new spec"
```

---

### Task 21: Version bump + manual smoke checklist

**Files:**
- Modify: `src/llm_cli/__init__.py`

- [ ] **Step 1: Bump the version to `0.2.0`**

In `src/llm_cli/__init__.py`, update `__version__` to `"0.2.0"`.

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests -q`
Expected: all green. If anything fails, fix it before continuing.

- [ ] **Step 3: Manual smoke (in WSL, against a real runtime)**

Walk through these manually and tick off:

- [ ] `llm --version` prints `0.2.0`.
- [ ] `llm setup --default` writes settings and prints the fixed hint panel.
- [ ] `llm setup` (interactive) walks the chain; saying "no" to every step exits 0 cleanly.
- [ ] `llm runtime setup` lists `llamacpp` and `stub-runtime` under the preset branch; install one without errors.
- [ ] `llm runtime setup` custom branch with template mode writes `manifest.yaml` + `serve.sh` + `healthcheck.sh` + `params.yaml` + `.installed`.
- [ ] `llm runtime install <custom-id>` errors with the kind-custom message.
- [ ] `llm config setup` picks a runtime, picks a model, walks params with `[estimate ...]` showing on `ctx` + `n_gpu_layers` for llamacpp, writes a valid YAML.
- [ ] `llm config new --runtime llamacpp --model <mid> --param gguf_path='${model_path}'` writes the same shape.
- [ ] `llm advisor --runtime llamacpp --model <mid>` prints estimates.
- [ ] `llm advisor --runtime llamacpp --model <mid> --json` outputs valid JSON.
- [ ] `llm advisor <config-id>` reads the config and prints estimates; offers `[c] create a config` chain.
- [ ] `llm config validate` is green on the new configs.
- [ ] `llm serve <new-config>` starts; `llm stop` cleans up.

- [ ] **Step 4: Commit the version bump**

```bash
git add src/llm_cli/__init__.py
git commit -m "chore: bump version to 0.2.0"
```

- [ ] **Step 5: Tag the release (optional)**

```bash
git tag -a v0.2.0 -m "0.2.0 — wizards, advisor, params.yaml split, kind: custom"
```

(Pushing is left to the user.)

---

## Self-review checklist

Before declaring the plan complete:

- **Spec coverage:** Walk §5.1 through §5.12 of the spec and §6 (CLI flows). Verify each is implemented by a task:
  - §5.1 params.yaml split → Tasks 1, 3, 4
  - §5.2 kind: official/custom → Tasks 2, 3, 4
  - §5.3 env contract → no new code (Task 15 emits a `serve.sh` template that documents the contract); existing `serve.py` already injects these
  - §5.4 recommendations → Task 9
  - §5.5 wizard primitives → Tasks 6, 7, 8
  - §5.6 chain orchestration → Task 17
  - §5.7 command surface + boundary errors → Tasks 10, 11, 12, 13, 14, 15, 16
  - §5.8 advisor → Tasks 10, 11, 16
  - §5.9 wizard rendering → Tasks 7, 8, 13
  - §5.10 config validate extensions → Tasks 1 (rejection of inline `serve:`), 2 (kind: custom + build), 13 (validate is called by `do_config_new` indirectly via the param coercion)
  - §5.11 wizard error handling → Tasks 13, 15 (atomic writes)
  - §5.12 history events → Task 15 (`runtime-setup`), the chain event is emitted by `chain.py` via `append_history` in Task 17 (add this as Step 4.5 below if missing)
- **Placeholder scan:** Grep the plan for `TBD`, `TODO`, `fill in`, `etc.`, `similar to`. Fix.
- **Type consistency:** `Recommendation` shape (value: str, reason: str); `RuntimeManifest.kind`; `ParamSpec.tier`/`.description`; `InstallRecord.kind` — all match across Tasks.
- **History events:** §5.12 mentions four new event kinds; verify `runtime-setup` is emitted (Task 15 step 3), `config-create` is emitted from `do_config_new` (add a `append_history({"action": "config-create", "id": cid, "via": "new"|"setup"})` call inside `do_config_new` if missing), `setup-chain` is emitted from `chain.run_setup_chain` (add to Task 17), `advisor` is emitted from `do_advisor` (add to Task 10).

If the self-review surfaces gaps, fix the relevant task(s) inline. No need to re-review.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-wizards-and-advisor.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration. Uses `superpowers:subagent-driven-development`.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?
