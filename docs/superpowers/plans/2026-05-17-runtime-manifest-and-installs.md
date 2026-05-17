# Runtime Manifests & Installs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make runtimes a first-class, schema-driven object: typed manifests, install lifecycle (`llm runtime [list|info|install|uninstall|rebuild]`), typed `serve.params` validated against runtime schemas, scoped `llm doctor`, and a `.installed` marker that gates `llm serve`.

**Architecture:** Two new core modules (`params.py` for the type system + path templating + when-clauses, `install_record.py` for the `.installed` JSON marker). `registry.py` grows a typed `RuntimeManifest` and tightens `validate_config`. `doctor.py` becomes scope-aware. Two new Typer sub-apps (`runtime`, `model`) replace top-level `build`/`pull`. Existing `llamacpp` + `stub-runtime` migrate to the new shape; the two existing configs flip from `serve.env` to `serve.params`. Docs follow.

**Tech Stack:** Python 3.11+, Typer, Rich, PyYAML, pytest, hashlib (stdlib), subprocess via the existing WSL runner.

**Spec:** [`docs/superpowers/specs/2026-05-17-runtime-manifest-and-installs.md`](../specs/2026-05-17-runtime-manifest-and-installs.md)

---

## Phase A — Param system (`core/params.py`)

### Task A1: ParamSpec dataclass + schema parsing

**Files:**
- Create: `src/llm_cli/core/params.py`
- Test: `tests/unit/test_params.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_params.py
from __future__ import annotations

import pytest

from llm_cli.core.params import ParamSpec, ParamType, parse_schema


def test_parse_schema_empty():
    assert parse_schema({}) == []


def test_parse_schema_basic_types():
    raw = {
        "flavor": {"type": "enum", "values": ["cuda", "cpu"], "default": "cuda"},
        "jobs": {"type": "int", "default": 0, "prompt": "Parallel jobs"},
        "ctx": {"type": "int", "default": 8192, "required": False},
        "name": {"type": "string", "required": True},
    }
    specs = parse_schema(raw)
    by_key = {s.key: s for s in specs}
    assert by_key["flavor"].type is ParamType.ENUM
    assert by_key["flavor"].values == ("cuda", "cpu")
    assert by_key["flavor"].default == "cuda"
    assert by_key["jobs"].type is ParamType.INT
    assert by_key["jobs"].prompt == "Parallel jobs"
    assert by_key["name"].required is True
    assert by_key["ctx"].required is False


def test_parse_schema_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown param type"):
        parse_schema({"x": {"type": "blob"}})


def test_parse_schema_enum_requires_values():
    with pytest.raises(ValueError, match="enum .* values"):
        parse_schema({"x": {"type": "enum"}})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_params.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Write the implementation**

```python
# src/llm_cli/core/params.py
"""Typed parameter system used by runtime build/serve schemas and configs."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParamType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    ENUM = "enum"
    PATH = "path"


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


def _coerce_type(raw: Any) -> ParamType:
    if not isinstance(raw, str):
        raise ValueError(f"param type must be a string, got {raw!r}")
    try:
        return ParamType(raw)
    except ValueError as exc:
        raise ValueError(
            f"unknown param type {raw!r}; "
            f"valid: {', '.join(t.value for t in ParamType)}"
        ) from exc


def parse_schema(raw: dict[str, Any]) -> list[ParamSpec]:
    """Parse a manifest schema mapping (`build:` or `serve:`) into ParamSpecs."""
    if not isinstance(raw, dict):
        raise ValueError(f"schema must be a mapping, got {type(raw).__name__}")
    out: list[ParamSpec] = []
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"param {key!r}: entry must be a mapping")
        ptype = _coerce_type(entry.get("type"))
        values: tuple[str, ...] = ()
        if ptype is ParamType.ENUM:
            raw_values = entry.get("values")
            if not isinstance(raw_values, list) or not raw_values:
                raise ValueError(
                    f"param {key!r}: enum requires a non-empty `values:` list"
                )
            values = tuple(str(v) for v in raw_values)
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
            )
        )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_params.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): ParamSpec dataclass and schema parsing"
```

---

### Task A2: Value validation for primitive types

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_params.py
from llm_cli.core.params import coerce_value, ParamValidationError


def _spec(key: str, type_: str, **kw) -> ParamSpec:
    return parse_schema({key: {"type": type_, **kw}})[0]


def test_coerce_string_passes_through():
    assert coerce_value(_spec("x", "string"), "hi") == "hi"


def test_coerce_int_parses_string_and_int():
    assert coerce_value(_spec("x", "int"), 42) == 42
    assert coerce_value(_spec("x", "int"), "42") == 42


def test_coerce_int_rejects_garbage():
    with pytest.raises(ParamValidationError):
        coerce_value(_spec("x", "int"), "fourty-two")


def test_coerce_float_parses():
    assert coerce_value(_spec("x", "float"), 1.5) == 1.5
    assert coerce_value(_spec("x", "float"), "0.9") == 0.9


def test_coerce_bool_accepts_true_false_strings():
    spec = _spec("x", "bool")
    for val in (True, "true", "1", "yes"):
        assert coerce_value(spec, val) is True
    for val in (False, "false", "0", "no"):
        assert coerce_value(spec, val) is False


def test_coerce_bool_rejects_other():
    with pytest.raises(ParamValidationError):
        coerce_value(_spec("x", "bool"), "maybe")


def test_coerce_enum_accepts_listed():
    spec = _spec("x", "enum", values=["a", "b"])
    assert coerce_value(spec, "a") == "a"


def test_coerce_enum_rejects_unlisted():
    spec = _spec("x", "enum", values=["a", "b"])
    with pytest.raises(ParamValidationError, match="must be one of"):
        coerce_value(spec, "c")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_params.py -v`
Expected: FAIL (`coerce_value` / `ParamValidationError` not defined).

- [ ] **Step 3: Add the implementation**

```python
# Append to src/llm_cli/core/params.py
class ParamValidationError(ValueError):
    """Raised when a value cannot be coerced/validated against its ParamSpec."""


_BOOL_TRUE = {"true", "1", "yes", "y", "on"}
_BOOL_FALSE = {"false", "0", "no", "n", "off"}


def coerce_value(spec: ParamSpec, raw: Any) -> Any:
    """Coerce a YAML scalar / CLI string into the spec's declared type.

    Path expansion is handled separately by `expand_path` after coercion;
    here we only validate that the raw value is a non-empty string-ish.
    """
    if spec.type is ParamType.STRING:
        return str(raw)
    if spec.type is ParamType.INT:
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ParamValidationError(
                f"param {spec.key!r}: expected int, got {raw!r}"
            ) from exc
    if spec.type is ParamType.FLOAT:
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ParamValidationError(
                f"param {spec.key!r}: expected float, got {raw!r}"
            ) from exc
    if spec.type is ParamType.BOOL:
        if isinstance(raw, bool):
            return raw
        token = str(raw).strip().lower()
        if token in _BOOL_TRUE:
            return True
        if token in _BOOL_FALSE:
            return False
        raise ParamValidationError(
            f"param {spec.key!r}: expected bool, got {raw!r}"
        )
    if spec.type is ParamType.ENUM:
        token = str(raw)
        if token not in spec.values:
            raise ParamValidationError(
                f"param {spec.key!r}: must be one of "
                f"{', '.join(spec.values)}; got {raw!r}"
            )
        return token
    if spec.type is ParamType.PATH:
        return str(raw)
    raise ParamValidationError(f"param {spec.key!r}: unhandled type {spec.type!r}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): coerce_value for string/int/float/bool/enum"
```

---

### Task A3: Path-type expansion

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_params.py
from pathlib import Path

from llm_cli.core.params import expand_path
from llm_cli.core.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        repo_root=tmp_path / "repo",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
    )


def test_expand_path_tokens(tmp_path):
    s = _settings(tmp_path)
    assert expand_path("${data_root}/x", s) == str((tmp_path / "data" / "x").as_posix())
    assert expand_path("${models_dir}/m.gguf", s) == str(
        (tmp_path / "data" / "models" / "m.gguf").as_posix()
    )


def test_expand_path_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    s = _settings(tmp_path)
    assert expand_path("~/foo", s).endswith("/foo")


def test_expand_path_unknown_token_raises(tmp_path):
    s = _settings(tmp_path)
    with pytest.raises(ParamValidationError, match="unknown template token"):
        expand_path("${nope}/x", s)


def test_expand_path_passthrough_when_no_token(tmp_path):
    s = _settings(tmp_path)
    assert expand_path("/abs/path", s) == "/abs/path"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: FAIL (`expand_path` not defined).

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/params.py
import re
from pathlib import Path

from llm_cli.core.settings import Settings

_TOKEN_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _settings_tokens(s: Settings) -> dict[str, str]:
    return {
        "data_root": s.data_root.as_posix(),
        "repo_root": s.repo_root.as_posix(),
        "runtimes_dir": s.runtimes_dir.as_posix(),
        "models_dir": s.models_dir.as_posix(),
        "cache_dir": s.cache_dir.as_posix(),
    }


def expand_path(raw: str, settings: Settings) -> str:
    """Expand ${data_root}/${runtimes_dir}/... and leading ~ in a path string.

    Unknown ${...} tokens raise ParamValidationError. No shell is involved.
    """
    tokens = _settings_tokens(settings)
    expanded = str(Path(raw).expanduser()) if raw.startswith("~") else raw

    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in tokens:
            raise ParamValidationError(
                f"unknown template token ${{{name}}}; "
                f"valid: {', '.join(sorted(tokens))}"
            )
        return tokens[name]

    return _TOKEN_RE.sub(_sub, expanded)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): path template expansion (\\${data_root} etc.) for path-typed params"
```

---

### Task A4: Env var name derivation

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_params.py
from llm_cli.core.params import derive_env_name


def test_derive_env_name_uses_declared_env():
    spec = _spec("gguf_path", "path", env="LLM_LLAMACPP_GGUF")
    assert derive_env_name(spec, runtime_id="llamacpp") == "LLM_LLAMACPP_GGUF"


def test_derive_env_name_fallback_runtime_serve():
    spec = _spec("ctx", "int")
    assert derive_env_name(spec, runtime_id="llamacpp") == "LLM_LLAMACPP_CTX"


def test_derive_env_name_fallback_build():
    spec = _spec("flavor", "enum", values=["a", "b"])
    assert derive_env_name(spec, runtime_id="llamacpp", scope="build") == "LLM_BUILD_FLAVOR"


def test_derive_env_name_normalizes_dashes():
    spec = _spec("n-gpu-layers", "int")
    assert derive_env_name(spec, runtime_id="llamacpp") == "LLM_LLAMACPP_N_GPU_LAYERS"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/params.py
def _normalize_token(token: str) -> str:
    return token.replace("-", "_").upper()


def derive_env_name(
    spec: ParamSpec, *, runtime_id: str, scope: str = "serve"
) -> str:
    """Resolve the env-var name for a param.

    Precedence:
    1. spec.env if declared.
    2. scope == "build" -> LLM_BUILD_<KEY> (runtime id intentionally omitted;
       build.sh sees a uniform contract regardless of runtime).
    3. otherwise -> LLM_<RUNTIME>_<KEY>.
    """
    if spec.env:
        return spec.env
    if scope == "build":
        return f"LLM_BUILD_{_normalize_token(spec.key)}"
    return f"LLM_{_normalize_token(runtime_id)}_{_normalize_token(spec.key)}"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): env var name derivation with build/serve scope fallback"
```

---

### Task A5: When-clause evaluation

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_params.py
from llm_cli.core.params import evaluate_when


def test_evaluate_when_none_passes():
    assert evaluate_when(None, build_params={"flavor": "cuda"}) is True
    assert evaluate_when({}, build_params={"flavor": "cuda"}) is True


def test_evaluate_when_matches():
    assert evaluate_when(
        {"build.flavor": "cuda"}, build_params={"flavor": "cuda"}
    ) is True


def test_evaluate_when_mismatches():
    assert evaluate_when(
        {"build.flavor": "cuda"}, build_params={"flavor": "cpu"}
    ) is False


def test_evaluate_when_param_absent_means_unknown():
    # Param wasn't supplied -> treat as "unknown", skip the requirement.
    assert evaluate_when(
        {"build.flavor": "cuda"}, build_params={}
    ) is False


def test_evaluate_when_rejects_non_build_prefix():
    with pytest.raises(ValueError, match="only build."):
        evaluate_when({"serve.host": "x"}, build_params={})
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/params.py
def evaluate_when(
    when: dict[str, Any] | None, *, build_params: dict[str, Any]
) -> bool:
    """Return True if a `requires:` entry's `when:` clause matches.

    v1 supports only `build.<param>: <scalar>` equality. Missing/None clause -> True.
    A reference to a param the user didn't supply returns False (skip the dep).
    """
    if not when:
        return True
    for key, expected in when.items():
        if not key.startswith("build."):
            raise ValueError(
                f"`when:` only supports build.<param> keys in v1; got {key!r}"
            )
        param = key[len("build.") :]
        if param not in build_params:
            return False
        if build_params[param] != expected:
            return False
    return True
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): when-clause evaluator (build.<param> equality)"
```

---

### Task A6: validate_params (unknown/missing/coerce in one pass)

**Files:**
- Modify: `src/llm_cli/core/params.py`
- Modify: `tests/unit/test_params.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_params.py
from llm_cli.core.params import validate_params


def test_validate_params_fills_defaults():
    specs = parse_schema(
        {
            "ctx": {"type": "int", "default": 8192},
            "host": {"type": "string", "default": "127.0.0.1"},
        }
    )
    out, errors = validate_params(specs, {})
    assert errors == []
    assert out == {"ctx": 8192, "host": "127.0.0.1"}


def test_validate_params_required_missing_errors():
    specs = parse_schema({"name": {"type": "string", "required": True}})
    out, errors = validate_params(specs, {})
    assert out == {}
    assert any("name" in e and "required" in e for e in errors)


def test_validate_params_unknown_key_errors():
    specs = parse_schema({"ctx": {"type": "int", "default": 8}})
    out, errors = validate_params(specs, {"ctxx": 16})
    assert out == {}
    assert any("unknown" in e and "ctxx" in e for e in errors)


def test_validate_params_type_mismatch_errors():
    specs = parse_schema({"ctx": {"type": "int", "default": 8}})
    out, errors = validate_params(specs, {"ctx": "huge"})
    assert out == {}
    assert any("ctx" in e for e in errors)


def test_validate_params_returns_coerced():
    specs = parse_schema({"jobs": {"type": "int", "default": 0}})
    out, errors = validate_params(specs, {"jobs": "4"})
    assert errors == []
    assert out == {"jobs": 4}
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/params.py
def validate_params(
    specs: list[ParamSpec], raw: dict[str, Any] | None
) -> tuple[dict[str, Any], list[str]]:
    """Validate a raw param map against `specs`. Returns (coerced, errors).

    Order of checks: unknown keys first (block); then per-spec coercion + required.
    On any error the coerced dict is empty so callers won't half-use bad input.
    """
    raw = dict(raw or {})
    errors: list[str] = []
    spec_by_key = {s.key: s for s in specs}

    for key in raw:
        if key not in spec_by_key:
            valid = ", ".join(sorted(spec_by_key)) or "(none)"
            errors.append(f"unknown param {key!r}; valid: {valid}")

    coerced: dict[str, Any] = {}
    for spec in specs:
        if spec.key in raw:
            try:
                coerced[spec.key] = coerce_value(spec, raw[spec.key])
            except ParamValidationError as exc:
                errors.append(str(exc))
        elif spec.required:
            errors.append(f"param {spec.key!r}: required")
        elif spec.default is not None:
            coerced[spec.key] = spec.default

    if errors:
        return {}, errors
    return coerced, []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_params.py -v`
Expected: PASS (all params tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/params.py tests/unit/test_params.py
git commit -m "feat(params): validate_params orchestrator (unknown/missing/coerce)"
```

---

## Phase B — Install record (`core/install_record.py`)

### Task B1: Read/write `.installed` round-trip

**Files:**
- Create: `src/llm_cli/core/install_record.py`
- Test: `tests/unit/test_install_record.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_install_record.py
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.install_record import (
    InstallRecord,
    is_installed,
    read_record,
    record_path,
    write_record,
)


def test_record_path(tmp_path: Path):
    assert record_path(tmp_path / "runtimes", "llamacpp") == (
        tmp_path / "runtimes" / "llamacpp" / ".installed"
    )


def test_write_and_read_round_trip(tmp_path: Path):
    rec = InstallRecord(
        runtime_id="llamacpp",
        installed_at="2026-05-17T17:45:00Z",
        build_params={"flavor": "cuda", "jobs": 0},
        build_sh_sha256="abc123",
        verify_passed=True,
        schema_hash="def456",
    )
    write_record(tmp_path / "runtimes", rec)
    got = read_record(tmp_path / "runtimes", "llamacpp")
    assert got == rec


def test_read_record_missing_returns_none(tmp_path: Path):
    assert read_record(tmp_path / "runtimes", "llamacpp") is None


def test_is_installed(tmp_path: Path):
    assert is_installed(tmp_path / "runtimes", "llamacpp") is False
    write_record(
        tmp_path / "runtimes",
        InstallRecord(
            runtime_id="llamacpp",
            installed_at="2026-05-17T17:45:00Z",
            build_params={},
            build_sh_sha256="x",
            verify_passed=None,
            schema_hash="y",
        ),
    )
    assert is_installed(tmp_path / "runtimes", "llamacpp") is True


def test_read_record_corrupt_raises(tmp_path: Path):
    p = tmp_path / "runtimes" / "llamacpp" / ".installed"
    p.parent.mkdir(parents=True)
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        read_record(tmp_path / "runtimes", "llamacpp")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_install_record.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implementation**

```python
# src/llm_cli/core/install_record.py
"""Persistence of a runtime's `.installed` marker file."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InstallRecord:
    runtime_id: str
    installed_at: str
    build_params: dict[str, Any] = field(default_factory=dict)
    build_sh_sha256: str = ""
    verify_passed: bool | None = None
    schema_hash: str = ""


def record_path(runtimes_dir: Path, runtime_id: str) -> Path:
    """Absolute path of <runtimes_dir>/<id>/.installed."""
    return runtimes_dir / runtime_id / ".installed"


def write_record(runtimes_dir: Path, rec: InstallRecord) -> Path:
    """Write the install record JSON; creates parent dirs as needed."""
    p = record_path(runtimes_dir, rec.runtime_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(asdict(rec), indent=2, sort_keys=True), encoding="utf-8"
    )
    return p


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
    )


def is_installed(runtimes_dir: Path, runtime_id: str) -> bool:
    return record_path(runtimes_dir, runtime_id).is_file()


def clear_record(runtimes_dir: Path, runtime_id: str) -> bool:
    p = record_path(runtimes_dir, runtime_id)
    if not p.is_file():
        return False
    p.unlink()
    return True
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/test_install_record.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/install_record.py tests/unit/test_install_record.py
git commit -m "feat(install-record): InstallRecord dataclass + JSON read/write"
```

---

### Task B2: sha256 helpers (build.sh + canonical schema hash)

**Files:**
- Modify: `src/llm_cli/core/install_record.py`
- Modify: `tests/unit/test_install_record.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_install_record.py
from llm_cli.core.install_record import file_sha256, schema_hash


def test_file_sha256(tmp_path: Path):
    p = tmp_path / "a.sh"
    p.write_text("hello\n", encoding="utf-8")
    # sha256("hello\n")
    assert file_sha256(p) == (
        "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    )


def test_file_sha256_missing_returns_empty(tmp_path: Path):
    assert file_sha256(tmp_path / "nope") == ""


def test_schema_hash_stable_across_key_order():
    a = {"flavor": {"type": "enum", "values": ["cuda", "cpu"], "default": "cuda"}}
    b = {"flavor": {"default": "cuda", "type": "enum", "values": ["cuda", "cpu"]}}
    assert schema_hash(a) == schema_hash(b)


def test_schema_hash_changes_on_value_change():
    a = {"jobs": {"type": "int", "default": 0}}
    b = {"jobs": {"type": "int", "default": 1}}
    assert schema_hash(a) != schema_hash(b)
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_install_record.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/install_record.py
import hashlib


def file_sha256(path: Path) -> str:
    """Return hex sha256 of a file's contents; '' if the file is missing."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def schema_hash(schema: dict[str, Any] | None) -> str:
    """Stable hex sha256 of a canonicalized schema mapping.

    Keys are sorted recursively so semantically-equal schemas produce the same
    hash regardless of YAML key order. Used by InstallRecord.schema_hash to
    flag drift between install time and the current manifest.
    """
    payload = json.dumps(schema or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_install_record.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/install_record.py tests/unit/test_install_record.py
git commit -m "feat(install-record): file_sha256 and stable schema_hash helpers"
```

---

## Phase C — Typed runtime manifest in `registry.py`

### Task C1: Typed RuntimeManifest exposed alongside RuntimeRecord

**Files:**
- Modify: `src/llm_cli/core/registry.py`
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_registry.py
def test_runtime_manifest_typed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "runtimes" / "rt-a").mkdir(parents=True)
    (repo / "runtimes" / "rt-a" / "manifest.yaml").write_text(
        "id: rt-a\n"
        "display_name: A\n"
        "official: true\n"
        "build:\n"
        "  flavor:\n"
        "    type: enum\n"
        "    values: [cuda, cpu]\n"
        "    default: cuda\n"
        "serve:\n"
        "  ctx:\n"
        "    type: int\n"
        "    default: 8192\n"
        "requires:\n"
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: 'v ([\\d.]+)', min: '3.16' }\n"
        "    install_hint: apt install cmake\n",
        encoding="utf-8",
    )
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (repo / "runtimes" / "rt-a" / s).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    mfs = registry.load_runtime_manifests(repo)
    assert len(mfs) == 1
    rt = mfs[0]
    assert rt.id == "rt-a"
    assert rt.official is True
    assert [s.key for s in rt.build_schema] == ["flavor"]
    assert rt.build_schema[0].values == ("cuda", "cpu")
    assert [s.key for s in rt.serve_schema] == ["ctx"]
    assert len(rt.requires) == 1
    assert rt.requires[0]["id"] == "cmake"
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_registry.py::test_runtime_manifest_typed -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/registry.py
from llm_cli.core.params import ParamSpec, parse_schema


@dataclass(frozen=True)
class RuntimeManifest:
    id: str
    display_name: str
    description: str
    official: bool
    build_schema: list[ParamSpec]
    serve_schema: list[ParamSpec]
    requires: list[dict[str, Any]]
    path: Path
    raw: dict[str, Any]


def _to_manifest(rec: RuntimeRecord) -> RuntimeManifest:
    data = rec.manifest
    requires = data.get("requires") or []
    if not isinstance(requires, list):
        raise ValueError(f"{rec.id}: requires must be a list")
    return RuntimeManifest(
        id=rec.id,
        display_name=str(data.get("display_name", rec.id)),
        description=str(data.get("description", "")),
        official=bool(data.get("official", False)),
        build_schema=parse_schema(data.get("build") or {}),
        serve_schema=parse_schema(data.get("serve") or {}),
        requires=[r for r in requires if isinstance(r, dict)],
        path=rec.path,
        raw=data,
    )


def load_runtime_manifests(repo: Path) -> list[RuntimeManifest]:
    return [_to_manifest(r) for r in discover_runtimes(repo)]


def get_runtime_manifest(repo: Path, runtime_id: str) -> RuntimeManifest | None:
    rec = get_runtime(repo, runtime_id)
    return _to_manifest(rec) if rec is not None else None
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/test_registry.py::test_runtime_manifest_typed -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(registry): typed RuntimeManifest (build/serve schemas, requires, official)"
```

---

### Task C2: `validate_config` validates `serve.params`, warns on uninstalled

**Files:**
- Modify: `src/llm_cli/core/registry.py`
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Replace the existing per-config helper used in tests + add new tests**

Replace the `_write_config` helper in `tests/unit/test_registry.py` with one that emits `serve.params` (and a `params:` schema on the runtime). Also extend the test to cover the new behaviors:

```python
# tests/unit/test_registry.py — update _write_runtime and _write_config:
def _write_runtime(
    repo: Path,
    rid: str,
    *,
    with_scripts: bool = True,
    serve_schema: dict | None = None,
) -> None:
    root = repo / "runtimes" / rid
    root.mkdir(parents=True)
    body = f"id: {rid}\ndisplay_name: {rid}\n"
    if serve_schema is not None:
        import yaml as _y
        body += "serve:\n" + _y.safe_dump(serve_schema, sort_keys=False)
    (root / "manifest.yaml").write_text(body, encoding="utf-8")
    if with_scripts:
        for name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (root / name).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def _write_config(
    repo: Path,
    cid: str,
    runtime: str,
    model: str,
    *,
    params: dict | None = None,
) -> None:
    (repo / "configs").mkdir(parents=True, exist_ok=True)
    import yaml as _y
    body = (
        f"id: {cid}\nruntime: {runtime}\nmodel: {model}\n"
        "serve:\n  host: 127.0.0.1\n  port: 1\n"
    )
    if params is not None:
        body += "  params:\n" + _y.safe_dump({"_": params}, sort_keys=False).replace(
            "_:\n", ""
        )
    (repo / "configs" / f"{cid}.yaml").write_text(body, encoding="utf-8")
```

Add tests:

```python
# Append to tests/unit/test_registry.py
def test_validate_config_rejects_unknown_param(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(
        repo,
        "rt-a",
        serve_schema={"ctx": {"type": "int", "default": 8}},
    )
    _write_model(repo, "md-a")
    _write_config(repo, "c1", "rt-a", "md-a", params={"ctxx": 16})
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("unknown param" in e and "ctxx" in e for e in errs)


def test_validate_config_required_param_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(
        repo,
        "rt-a",
        serve_schema={"gguf": {"type": "string", "required": True}},
    )
    _write_model(repo, "md-a")
    _write_config(repo, "c1", "rt-a", "md-a", params={})
    cfg = registry.discover_configs(repo)[0]
    errs = registry.validate_config(repo, cfg)
    assert any("required" in e for e in errs)


def test_validate_config_warns_uninstalled_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _settings(tmp_path, repo)
    _write_runtime(
        repo,
        "rt-a",
        serve_schema={"ctx": {"type": "int", "default": 8}},
    )
    _write_model(repo, "md-a")
    _write_config(repo, "c1", "rt-a", "md-a", params={"ctx": 16})
    cfg = registry.discover_configs(repo)[0]
    errs, warnings = registry.validate_config_v2(repo, cfg)
    assert errs == []
    assert any("not installed" in w for w in warnings)
```

Also: the **existing happy-path test** (`test_discover_and_validate_happy_path`) needs updating — its old shape (`serve:` with `host`/`port` only) now succeeds against an empty `serve_schema` (existing helpers default to no schema). Keep it as is; it stays green.

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_registry.py -v`
Expected: FAIL on the new tests (and the old happy path may break depending on schema strictness — confirm before continuing).

- [ ] **Step 3: Update `validate_config` and introduce `validate_config_v2`**

```python
# Modify src/llm_cli/core/registry.py: extend imports and add new function
from llm_cli.core.install_record import is_installed
from llm_cli.core.params import validate_params


def validate_config_v2(
    repo: Path, cfg: ConfigRecord
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors fail validation; warnings are advisory."""
    errors: list[str] = []
    warnings: list[str] = []

    rt_id = cfg.data.get("runtime")
    md_id = cfg.data.get("model")
    if not isinstance(rt_id, str):
        errors.append(f"{cfg.id}: runtime must be a string")
        return errors, warnings
    if not isinstance(md_id, str):
        errors.append(f"{cfg.id}: model must be a string")
        return errors, warnings

    rt_manifest = get_runtime_manifest(repo, rt_id)
    if rt_manifest is None:
        errors.append(f"{cfg.id}: unknown runtime {rt_id!r}")
    else:
        errors.extend(validate_runtime_layout(get_runtime(repo, rt_id)))

    md = get_model(repo, md_id)
    if md is None:
        errors.append(f"{cfg.id}: unknown model {md_id!r}")
    else:
        errors.extend(validate_model_layout(md))

    serve = cfg.data.get("serve")
    if not isinstance(serve, dict):
        errors.append(f"{cfg.id}: serve must be a mapping")
    else:
        for key in ("host", "port"):
            if key not in serve:
                errors.append(f"{cfg.id}: serve.{key} is required")
        if rt_manifest is not None:
            params = serve.get("params")
            if params is not None and not isinstance(params, dict):
                errors.append(f"{cfg.id}: serve.params must be a mapping")
            else:
                _, perrs = validate_params(rt_manifest.serve_schema, params)
                errors.extend(f"{cfg.id}: {e}" for e in perrs)

    ready = cfg.data.get("readiness")
    if ready is not None and not isinstance(ready, dict):
        errors.append(f"{cfg.id}: readiness must be a mapping when present")

    yaml_id = cfg.data.get("id")
    if yaml_id is not None and yaml_id != cfg.id:
        errors.append(f"{cfg.id}: file id {yaml_id!r} does not match filename")

    try:
        settings = resolve(load_settings())
    except (MissingSettingError, UnknownSettingError, ValueError) as exc:
        errors.append(f"settings: {exc}")
        return errors, warnings

    if rt_manifest is not None and not is_installed(settings.runtimes_dir, rt_id):
        warnings.append(
            f"{cfg.id}: runtime {rt_id!r} is not installed; "
            f"run `llm runtime install {rt_id}` before `llm serve`."
        )

    return errors, warnings


def validate_config(repo: Path, cfg: ConfigRecord) -> list[str]:
    """Legacy errors-only wrapper used by older callers (kept for compatibility)."""
    errors, _ = validate_config_v2(repo, cfg)
    return errors
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(registry): validate_config_v2 - typed serve.params + uninstalled warning"
```

---

## Phase D — Doctor scoping (`core/doctor.py` + `commands/doctor.py`)

### Task D1: Per-runtime requirement loading + when-clause filtering

**Files:**
- Modify: `src/llm_cli/core/doctor.py`
- Test: `tests/unit/test_doctor_runtime_scope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_doctor_runtime_scope.py
from __future__ import annotations

from pathlib import Path

from llm_cli.core import doctor


def _write_runtime(repo: Path, rid: str, requires: list[dict]) -> None:
    root = repo / "runtimes" / rid
    root.mkdir(parents=True)
    import yaml as _y
    body = {
        "id": rid,
        "display_name": rid,
        "official": True,
        "build": {"flavor": {"type": "enum", "values": ["cuda", "cpu"], "default": "cuda"}},
        "requires": requires,
    }
    (root / "manifest.yaml").write_text(_y.safe_dump(body, sort_keys=False), encoding="utf-8")
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (root / s).write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def test_requirements_for_runtime_filters_by_when(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_runtime(
        repo,
        "rt-a",
        [
            {
                "id": "cmake",
                "name": "cmake",
                "verify": {"cmd": "cmake --version", "version_regex": "([\\d.]+)", "min": "3.16"},
                "install_hint": "apt install cmake",
            },
            {
                "id": "nvcc",
                "name": "nvcc",
                "when": {"build.flavor": "cuda"},
                "verify": {"cmd": "nvcc --version", "version_regex": "([\\d.]+)", "min": "12.0"},
                "install_hint": "install cuda",
            },
        ],
    )

    cuda = doctor.requirements_for_runtime(repo, "rt-a", build_params={"flavor": "cuda"})
    cpu = doctor.requirements_for_runtime(repo, "rt-a", build_params={"flavor": "cpu"})

    assert sorted(r.id for r in cuda) == ["cmake", "nvcc"]
    assert sorted(r.id for r in cpu) == ["cmake"]
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_doctor_runtime_scope.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation — add helpers to `core/doctor.py`**

```python
# Append to src/llm_cli/core/doctor.py
from typing import Any

from llm_cli.core import registry as _registry
from llm_cli.core.params import evaluate_when


def _req_from_entry(entry: dict[str, Any], owner: str) -> Requirement | None:
    if "id" not in entry or "verify" not in entry:
        return None
    verify = entry["verify"]
    if not isinstance(verify, dict) or "cmd" not in verify or "version_regex" not in verify:
        return None
    return Requirement(
        id=str(entry["id"]),
        name=str(entry.get("name", entry["id"])),
        why=str(entry.get("why", f"required by {owner}")),
        verify_cmd=str(verify["cmd"]),
        version_regex=str(verify["version_regex"]),
        min_version=verify.get("min"),
        install_hint=str(entry.get("install_hint", "")),
    )


def requirements_for_runtime(
    repo: Path, runtime_id: str, *, build_params: dict[str, Any]
) -> list[Requirement]:
    """Return requirements declared by a single runtime, filtered by `when:` clauses."""
    mf = _registry.get_runtime_manifest(repo, runtime_id)
    if mf is None:
        return []
    out: list[Requirement] = []
    for entry in mf.requires:
        if not evaluate_when(entry.get("when"), build_params=build_params):
            continue
        req = _req_from_entry(entry, owner=runtime_id)
        if req is not None:
            out.append(req)
    return out
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/test_doctor_runtime_scope.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/doctor.py tests/unit/test_doctor_runtime_scope.py
git commit -m "feat(doctor): requirements_for_runtime with when-clause filtering"
```

---

### Task D2: `requirements_for_all_runtimes` (with default-fill for `--all`)

**Files:**
- Modify: `src/llm_cli/core/doctor.py`
- Modify: `tests/unit/test_doctor_runtime_scope.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/unit/test_doctor_runtime_scope.py
from llm_cli.core.install_record import InstallRecord, write_record


def test_requirements_for_all_runtimes_uses_install_record_or_defaults(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_runtime(
        repo,
        "rt-a",
        [
            {"id": "cmake", "verify": {"cmd": "cmake", "version_regex": "([\\d.]+)", "min": "3.16"}, "install_hint": ""},
            {"id": "nvcc", "when": {"build.flavor": "cuda"},
             "verify": {"cmd": "nvcc", "version_regex": "([\\d.]+)", "min": "12.0"}, "install_hint": ""},
        ],
    )
    _write_runtime(
        repo,
        "rt-b",
        [{"id": "git", "verify": {"cmd": "git --version", "version_regex": "([\\d.]+)", "min": "2.30"}, "install_hint": ""}],
    )

    runtimes_dir = tmp_path / "data" / "runtimes"
    runtimes_dir.mkdir(parents=True)
    write_record(
        runtimes_dir,
        InstallRecord(
            runtime_id="rt-a",
            installed_at="2026-05-17T00:00:00Z",
            build_params={"flavor": "cpu"},
            build_sh_sha256="x",
            verify_passed=True,
            schema_hash="y",
        ),
    )

    # installed_only=True: rt-a is installed with flavor=cpu (skip nvcc); rt-b not installed.
    installed = doctor.requirements_for_all_runtimes(repo, runtimes_dir, installed_only=True)
    assert sorted(r.id for r in installed) == ["cmake"]

    # all_runtimes=True: rt-a uses install record (cpu, no nvcc); rt-b uses defaults.
    all_reqs = doctor.requirements_for_all_runtimes(repo, runtimes_dir, installed_only=False)
    assert sorted(r.id for r in all_reqs) == ["cmake", "git"]
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_doctor_runtime_scope.py::test_requirements_for_all_runtimes_uses_install_record_or_defaults -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/doctor.py
from llm_cli.core.install_record import read_record


def _default_build_params(mf: "_registry.RuntimeManifest") -> dict[str, Any]:
    return {s.key: s.default for s in mf.build_schema if s.default is not None}


def requirements_for_all_runtimes(
    repo: Path, runtimes_dir: Path, *, installed_only: bool
) -> list[Requirement]:
    """Aggregate per-runtime requirements.

    - installed_only=True: only runtimes whose `.installed` exists.
      Build params come from the install record (so `when:` evaluates correctly).
    - installed_only=False: every runtime in the repo. Build params come from
      the install record if present, else from schema defaults.
    """
    out: list[Requirement] = []
    seen: set[str] = set()
    for mf in _registry.load_runtime_manifests(repo):
        rec = read_record(runtimes_dir, mf.id)
        if installed_only and rec is None:
            continue
        build_params = dict(rec.build_params) if rec is not None else _default_build_params(mf)
        for req in requirements_for_runtime(repo, mf.id, build_params=build_params):
            # de-dup by id keeping first occurrence
            if req.id in seen:
                continue
            seen.add(req.id)
            out.append(req)
    return out
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/test_doctor_runtime_scope.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/doctor.py tests/unit/test_doctor_runtime_scope.py
git commit -m "feat(doctor): requirements_for_all_runtimes (installed-only and full sweep)"
```

---

### Task D3: `llm doctor` flags — `--runtime`, `--all`

**Files:**
- Modify: `src/llm_cli/commands/doctor.py`
- Modify: `tests/integration/test_cli_doctor.py` (add cases)

- [ ] **Step 1: Append failing integration test**

```python
# Append to tests/integration/test_cli_doctor.py
def test_doctor_default_scopes_to_installed_runtime_deps(tmp_path, monkeypatch):
    from llm_cli.core.install_record import InstallRecord, write_record
    from llm_cli.core.settings import save_settings

    repo = tmp_path / "repo"
    repo.mkdir()
    # Universal req: a no-op fake. Skip writing requirements.yaml to keep this minimal.
    (repo / "requirements.yaml").write_text("[]\n", encoding="utf-8")
    rt = repo / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: rt-a\n"
        "official: true\n"
        "requires:\n"
        "  - id: definitely-not-on-path-zzz\n"
        "    verify: { cmd: definitely-not-on-path-zzz, version_regex: '([0-9.]+)' }\n"
        "    install_hint: nope\n",
        encoding="utf-8",
    )
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / s).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    runtimes_dir = tmp_path / "data" / "runtimes"
    runtimes_dir.mkdir(parents=True)
    write_record(
        runtimes_dir,
        InstallRecord(
            runtime_id="rt-a",
            installed_at="2026-05-17T00:00:00Z",
            build_params={},
            build_sh_sha256="x",
            verify_passed=True,
            schema_hash="y",
        ),
    )
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    monkeypatch.chdir(repo)
    from typer.testing import CliRunner

    from llm_cli.main import app

    result = CliRunner().invoke(app, ["doctor"], catch_exceptions=False)
    assert "definitely-not-on-path-zzz" in result.stdout
    assert result.exit_code == 1
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_cli_doctor.py::test_doctor_default_scopes_to_installed_runtime_deps -v`
Expected: FAIL.

- [ ] **Step 3: Update `commands/doctor.py` to add flags and merge requirements**

```python
# src/llm_cli/commands/doctor.py — replace `doctor` callback
@doctor_app.callback()
def doctor(
    ctx: typer.Context,
    runtime: str | None = typer.Option(
        None, "--runtime", help="Scope to a single runtime's requirements."
    ),
    all_runtimes: bool = typer.Option(
        False, "--all", help="Include every runtime's deps (installed or not)."
    ),
) -> None:
    """Run requirement checks: universal + (per-flags scope) and print a table."""
    if ctx.invoked_subcommand is not None:
        return

    repo = repo_root()
    universal = load_requirements(_requirements_yaml(repo))

    from llm_cli.core.doctor import (
        requirements_for_all_runtimes,
        requirements_for_runtime,
    )
    from llm_cli.core.settings import load_settings, resolve as _resolve

    try:
        settings = _resolve(load_settings())
    except Exception as exc:  # noqa: BLE001 — surface as a doctor failure
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    extras: list = []
    if runtime is not None:
        from llm_cli.core.install_record import read_record

        rec = read_record(settings.runtimes_dir, runtime)
        build_params = dict(rec.build_params) if rec is not None else {}
        extras = requirements_for_runtime(repo, runtime, build_params=build_params)
    elif all_runtimes:
        extras = requirements_for_all_runtimes(repo, settings.runtimes_dir, installed_only=False)
    else:
        extras = requirements_for_all_runtimes(repo, settings.runtimes_dir, installed_only=True)

    seen = {r.id for r in universal}
    merged = list(universal) + [r for r in extras if r.id not in seen]
    results = check_all(merged)

    table = Table(title="External Requirements")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Detected")
    table.add_column("Min")
    table.add_column("Hint", overflow="fold")

    bad = 0
    for r in results:
        style = _STATUS_STYLES.get(r.status, "white")
        if r.status not in (CheckStatus.OK,):
            bad += 1
        table.add_row(
            r.requirement.id,
            r.requirement.name,
            f"[{style}]{r.status.value}[/{style}]",
            r.detected_version or "-",
            r.requirement.min_version or "-",
            r.requirement.install_hint if r.status != CheckStatus.OK else "",
        )

    console.print(table)
    linger = systemd_linger_advisory()
    if linger:
        console.print("[yellow]advisory (systemd-linger):[/yellow] " + linger)
    if bad:
        console.print(f"[red]{bad} requirement(s) need attention[/red]")
        raise typer.Exit(code=1)
    console.print("[green]all requirements satisfied[/green]")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_doctor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/doctor.py tests/integration/test_cli_doctor.py
git commit -m "feat(doctor): scoped checks - default=installed, --runtime, --all"
```

---

### Task D4: `render-requirements` adds per-runtime sections

**Files:**
- Modify: `src/llm_cli/core/doctor.py`
- Modify: `src/llm_cli/commands/doctor.py`
- Modify: `tests/unit/test_doctor_render.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/unit/test_doctor_render.py
from llm_cli.core.doctor import render_requirements_md_grouped, Requirement


def test_render_requirements_md_grouped_has_universal_and_runtime_sections():
    universal = [
        Requirement(
            id="python", name="Python", why="base",
            verify_cmd="python3 --version", version_regex="([\\d.]+)",
            min_version="3.11", install_hint="",
        )
    ]
    by_runtime = {
        "llamacpp": [
            Requirement(
                id="cmake", name="cmake", why="builds llama.cpp",
                verify_cmd="cmake --version", version_regex="([\\d.]+)",
                min_version="3.16", install_hint="apt install cmake",
            )
        ]
    }
    md = render_requirements_md_grouped(universal, by_runtime)
    assert "## Universal" in md
    assert "## Runtime: llamacpp" in md
    assert "python" in md
    assert "cmake" in md
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_doctor_render.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/core/doctor.py
def _render_table(reqs: list[Requirement]) -> list[str]:
    lines = ["| ID | Name | Min | Verify | Install | Why |", "|---|---|---|---|---|---|"]
    for req in reqs:
        min_v = req.min_version if req.min_version else "—"
        lines.append(
            "| {id} | {name} | {min} | `{verify}` | {install} | {why} |".format(
                id=_escape_pipes(req.id),
                name=_escape_pipes(req.name),
                min=_escape_pipes(min_v),
                verify=_escape_pipes(req.verify_cmd),
                install=_escape_pipes(req.install_hint),
                why=_escape_pipes(req.why),
            )
        )
    return lines


def render_requirements_md_grouped(
    universal: list[Requirement], by_runtime: dict[str, list[Requirement]]
) -> str:
    lines: list[str] = [_REQ_HEADER.rstrip(), "", "## Universal", ""]
    lines.extend(_render_table(universal))
    for rid in sorted(by_runtime):
        lines.extend(["", f"## Runtime: {rid}", ""])
        lines.extend(_render_table(by_runtime[rid]))
    return "\n".join(lines) + "\n"
```

```python
# Modify src/llm_cli/commands/doctor.py — render_requirements
@doctor_app.command(
    "render-requirements", help="Regenerate requirements.md (universal + per-runtime)."
)
def render_requirements() -> None:
    from llm_cli.core import registry as _reg
    from llm_cli.core.doctor import (
        render_requirements_md_grouped,
        requirements_for_runtime,
    )

    repo = repo_root()
    universal = load_requirements(_requirements_yaml(repo))
    by_runtime: dict[str, list] = {}
    for mf in _reg.load_runtime_manifests(repo):
        defaults = {s.key: s.default for s in mf.build_schema if s.default is not None}
        reqs = requirements_for_runtime(repo, mf.id, build_params=defaults)
        if reqs:
            by_runtime[mf.id] = reqs
    md = render_requirements_md_grouped(universal, by_runtime)
    out = repo / "requirements.md"
    out.write_text(md, encoding="utf-8")
    console.print(f"[green]wrote[/green] {out}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_doctor_render.py tests/integration/test_cli_doctor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/doctor.py src/llm_cli/commands/doctor.py tests/unit/test_doctor_render.py
git commit -m "feat(doctor): render-requirements emits universal + per-runtime sections"
```

---

## Phase E — `llm runtime` sub-app

### Task E1: `commands/runtime_cmd.py` scaffold + `list` subcommand

**Files:**
- Create: `src/llm_cli/commands/runtime_cmd.py`
- Test: `tests/integration/test_cli_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_runtime.py
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_cli.core.install_record import InstallRecord, write_record
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _scaffold(repo_root_dir: Path, runtimes_dir: Path) -> None:
    repo_root_dir.mkdir(parents=True, exist_ok=True)
    rt = repo_root_dir / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: rt-a\ndisplay_name: Alpha\nofficial: true\n", encoding="utf-8"
    )
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / s).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    rt2 = repo_root_dir / "runtimes" / "rt-b"
    rt2.mkdir(parents=True)
    (rt2 / "manifest.yaml").write_text(
        "id: rt-b\ndisplay_name: Beta\n", encoding="utf-8"
    )
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt2 / s).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    runtimes_dir.mkdir(parents=True, exist_ok=True)
    write_record(
        runtimes_dir,
        InstallRecord(
            runtime_id="rt-a",
            installed_at="2026-05-17T00:00:00Z",
            build_params={},
            build_sh_sha256="x",
            verify_passed=True,
            schema_hash="y",
        ),
    )


def test_runtime_list_shows_official_and_installed(tmp_path: Path):
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(app, ["runtime", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "rt-a" in result.stdout
    assert "rt-b" in result.stdout
    # Heuristic columns: "official" and "installed" markers visible
    assert "official" in result.stdout.lower() or "yes" in result.stdout.lower()
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: FAIL (sub-app not registered).

- [ ] **Step 3: Create the sub-app + list command + wire into main**

```python
# src/llm_cli/commands/runtime_cmd.py
"""`llm runtime` — manage runtime installs."""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core import registry
from llm_cli.core.install_record import is_installed, read_record
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve

console = Console()
runtime_app = typer.Typer(help="Manage runtime installs (list/info/install/uninstall/rebuild).")


def _settings():
    return resolve(load_settings())


@runtime_app.command("list", help="List runtimes with install state.")
def runtime_list(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    repo = repo_root()
    settings = _settings()
    manifests = registry.load_runtime_manifests(repo)

    rows: list[dict] = []
    for mf in manifests:
        rec = read_record(settings.runtimes_dir, mf.id)
        rows.append(
            {
                "id": mf.id,
                "display_name": mf.display_name,
                "official": mf.official,
                "installed": rec is not None,
                "installed_at": rec.installed_at if rec else None,
                "build_params": dict(rec.build_params) if rec else None,
            }
        )

    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return

    table = Table(title="Runtimes")
    table.add_column("ID")
    table.add_column("Display")
    table.add_column("Official")
    table.add_column("Installed")
    table.add_column("Build params")
    for row in rows:
        bp = row["build_params"]
        bp_text = ", ".join(f"{k}={v}" for k, v in (bp or {}).items()) if bp else "-"
        table.add_row(
            row["id"],
            row["display_name"],
            "yes" if row["official"] else "no",
            "yes" if row["installed"] else "no",
            bp_text,
        )
    console.print(table)
```

```python
# src/llm_cli/main.py — replace imports/registrations:
from llm_cli.commands import config_cmd, list_cmd
from llm_cli.commands import setup as setup_cmd
from llm_cli.commands import specs as specs_cmd
from llm_cli.commands import lifecycle_cmds
from llm_cli.commands import serve as serve_cmd
from llm_cli.commands.doctor import doctor_app
from llm_cli.commands.runtime_cmd import runtime_app
from llm_cli.commands.settings_cmd import settings_app
```

Replace the `add_typer`/`command` block to register the sub-app (we'll add `model_app` in Phase F; for this task, just remove `build`/`pull` registrations entirely is premature — keep them until Phase H Task H2 if it breaks tests. For this task, add the `runtime_app` mount **only**):

```python
# Insert into src/llm_cli/main.py just below `app.add_typer(settings_app, name="settings")`
app.add_typer(runtime_app, name="runtime")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py src/llm_cli/main.py tests/integration/test_cli_runtime.py
git commit -m "feat(runtime): runtime_app sub-app with `list` command"
```

---

### Task E2: `llm runtime info <id>`

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/integration/test_cli_runtime.py
def test_runtime_info_shows_install_and_schema(tmp_path: Path):
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["runtime", "info", "rt-a"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "rt-a" in result.stdout
    assert "installed" in result.stdout.lower()


def test_runtime_info_unknown_id(tmp_path: Path):
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["runtime", "info", "no-such"], catch_exceptions=False)
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/commands/runtime_cmd.py
from llm_cli.core.install_record import file_sha256, schema_hash


@runtime_app.command("info", help="Show manifest, install record, and drift.")
def runtime_info(runtime_id: str = typer.Argument(...)) -> None:
    repo = repo_root()
    settings = _settings()
    mf = registry.get_runtime_manifest(repo, runtime_id)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)

    console.print(f"[bold]{mf.id}[/bold] — {mf.display_name}")
    console.print(f"official: {'yes' if mf.official else 'no'}")
    if mf.description:
        console.print(f"description: {mf.description}")

    if mf.build_schema:
        console.print("\n[bold]build params:[/bold]")
        for s in mf.build_schema:
            console.print(f"  - {s.key} ({s.type.value})"
                          + (f" default={s.default!r}" if s.default is not None else "")
                          + (" required" if s.required else ""))
    if mf.serve_schema:
        console.print("\n[bold]serve params:[/bold]")
        for s in mf.serve_schema:
            console.print(f"  - {s.key} ({s.type.value})"
                          + (f" default={s.default!r}" if s.default is not None else "")
                          + (" required" if s.required else ""))

    rec = read_record(settings.runtimes_dir, mf.id)
    if rec is None:
        console.print("\n[yellow]not installed[/yellow]")
        console.print(f"hint: llm runtime install {mf.id}")
        return

    console.print("\n[bold]install:[/bold] [green]installed[/green]")
    console.print(f"installed_at: {rec.installed_at}")
    console.print(f"verify_passed: {rec.verify_passed}")
    if rec.build_params:
        bp = ", ".join(f"{k}={v}" for k, v in rec.build_params.items())
        console.print(f"build_params: {bp}")

    cur_sha = file_sha256(mf.path / "build.sh")
    if rec.build_sh_sha256 and cur_sha and cur_sha != rec.build_sh_sha256:
        console.print(
            "[yellow]drift:[/yellow] build.sh has changed since install "
            f"({rec.build_sh_sha256[:8]} -> {cur_sha[:8]})"
        )
    cur_schema = schema_hash(mf.raw.get("build") or {})
    if rec.schema_hash and cur_schema and cur_schema != rec.schema_hash:
        console.print(
            "[yellow]drift:[/yellow] build schema changed since install; "
            f"run `llm runtime rebuild {mf.id} --reset` to refresh"
        )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/integration/test_cli_runtime.py
git commit -m "feat(runtime): runtime info shows schema, install record, drift"
```

---

### Task E3: `llm runtime install <id>` — param resolution + dispatch

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/integration/test_cli_runtime.py
from unittest.mock import patch


def _scaffold_llamacpp(repo: Path) -> None:
    rt = repo / "runtimes" / "llamacpp"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: llamacpp\nofficial: true\n"
        "build:\n"
        "  flavor:\n    type: enum\n    values: [cuda, cpu]\n    default: cpu\n"
        "  jobs:\n    type: int\n    default: 0\n"
        "serve:\n"
        "  ctx:\n    type: int\n    default: 8192\n",
        encoding="utf-8",
    )
    for s in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / s).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_install_writes_record_with_defaults(mock_verify, mock_build, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (tmp_path / "data" / "runtimes" / "llamacpp").mkdir(parents=True)
    # Stub doctor to "all green" by giving the runtime no `requires:`.
    result = runner.invoke(app, ["runtime", "install", "llamacpp", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "llamacpp")
    assert rec is not None
    assert rec.build_params == {"flavor": "cpu", "jobs": 0}
    assert rec.verify_passed is True
    mock_build.assert_called_once()
    env = mock_build.call_args.kwargs["env"]
    assert env["LLM_BUILD_FLAVOR"] == "cpu"
    assert env["LLM_BUILD_JOBS"] == "0"


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_install_param_override(mock_verify, mock_build, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(
        app,
        ["runtime", "install", "llamacpp", "--yes", "--param", "flavor=cuda", "--param", "jobs=4"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "llamacpp")
    assert rec.build_params == {"flavor": "cuda", "jobs": 4}


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=1)
def test_runtime_install_build_failure_no_record(mock_build, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["runtime", "install", "llamacpp", "--yes"], catch_exceptions=False)
    assert result.exit_code != 0
    assert read_record(tmp_path / "data" / "runtimes", "llamacpp") is None
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/commands/runtime_cmd.py
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from llm_cli.core.install_record import InstallRecord, write_record
from llm_cli.core.lifecycle import append_history
from llm_cli.core.params import (
    ParamValidationError,
    derive_env_name,
    validate_params,
)
from llm_cli.core.wsl import is_windows, to_wsl_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_param_flag(token: str) -> tuple[str, str]:
    if "=" not in token:
        raise typer.BadParameter(f"--param must be key=value (got {token!r})")
    k, v = token.split("=", 1)
    return k.strip(), v.strip()


def _resolve_build_params(
    schema, *, flags: list[str], yes: bool
) -> dict[str, Any]:
    from_flags: dict[str, Any] = {}
    for tok in flags:
        k, v = _parse_param_flag(tok)
        from_flags[k] = v

    raw: dict[str, Any] = dict(from_flags)
    for s in schema:
        if s.key in raw:
            continue
        if yes:
            if s.default is None and s.required:
                raise typer.BadParameter(f"--yes set but {s.key} has no default")
            continue
        prompt = s.prompt or s.key
        default = s.default if s.default is not None else ""
        answer = typer.prompt(prompt, default=str(default))
        raw[s.key] = answer

    coerced, errors = validate_params(schema, raw)
    if errors:
        for e in errors:
            console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)
    return coerced


def _build_env(
    runtime_id: str, schema, build_params: dict[str, Any]
) -> dict[str, str]:
    env = os.environ.copy()
    for s in schema:
        name = derive_env_name(s, runtime_id=runtime_id, scope="build")
        if s.key in build_params:
            env[name] = str(build_params[s.key])
    return env


def _run_build_script(
    *, runtime_id: str, repo: Path, env: dict[str, str]
) -> int:
    """Run runtimes/<id>/build.sh via WSL bash and return exit code."""
    from llm_cli.core.wsl import run_repo_bash
    from llm_cli.core.settings import load_settings, resolve as _r

    return run_repo_bash(
        _r(load_settings()),
        f"runtimes/{runtime_id}/build.sh",
        extra_env={k: v for k, v in env.items() if k.startswith("LLM_BUILD_")},
    )


def _run_verify_script(
    *, runtime_id: str, repo: Path, env: dict[str, str]
) -> int | None:
    """Run runtimes/<id>/verify.sh if present; return exit code or None if absent."""
    p = repo / "runtimes" / runtime_id / "verify.sh"
    if not p.is_file():
        return None
    from llm_cli.core.wsl import run_repo_bash
    from llm_cli.core.settings import load_settings, resolve as _r

    return run_repo_bash(
        _r(load_settings()),
        f"runtimes/{runtime_id}/verify.sh",
        extra_env={k: v for k, v in env.items() if k.startswith("LLM_BUILD_")},
    )


def _pre_flight(repo: Path, runtime_id: str, build_params: dict[str, Any]) -> None:
    from llm_cli.core.doctor import (
        check_all,
        requirements_for_runtime,
    )

    reqs = requirements_for_runtime(repo, runtime_id, build_params=build_params)
    if not reqs:
        return
    results = check_all(reqs)
    bad = [r for r in results if r.status.value != "ok"]
    if bad:
        for r in bad:
            console.print(
                f"[red]missing:[/red] {r.requirement.id} ({r.status.value}). "
                f"hint: {r.requirement.install_hint or 'install manually'}"
            )
        raise typer.Exit(code=1)


@runtime_app.command("install", help="Install a runtime (interactive prompts).")
def runtime_install(
    runtime_id: str = typer.Argument(...),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Accept all defaults; skip prompts."
    ),
) -> None:
    repo = repo_root()
    settings = _settings()
    mf = registry.get_runtime_manifest(repo, runtime_id)
    if mf is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)

    try:
        build_params = _resolve_build_params(mf.build_schema, flags=param, yes=yes)
    except ParamValidationError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _pre_flight(repo, runtime_id, build_params)

    env = _build_env(runtime_id, mf.build_schema, build_params)
    rc = _run_build_script(runtime_id=runtime_id, repo=repo, env=env)
    if rc != 0:
        console.print(f"[red]build failed[/red] (exit {rc})")
        raise typer.Exit(code=rc)

    vrc = _run_verify_script(runtime_id=runtime_id, repo=repo, env=env)
    if vrc not in (None, 0):
        console.print(f"[red]verify failed[/red] (exit {vrc})")
        raise typer.Exit(code=vrc)

    from llm_cli.core.install_record import file_sha256, schema_hash

    rec = InstallRecord(
        runtime_id=runtime_id,
        installed_at=_utc_now_iso(),
        build_params=build_params,
        build_sh_sha256=file_sha256(mf.path / "build.sh"),
        verify_passed=True if vrc == 0 else None,
        schema_hash=schema_hash(mf.raw.get("build") or {}),
    )
    write_record(settings.runtimes_dir, rec)
    append_history(
        repo,
        {"action": "runtime-install", "id": runtime_id, "build_params": build_params},
    )
    summary = ", ".join(f"{k}={v}" for k, v in build_params.items()) or "no params"
    console.print(f"[green]installed[/green] {runtime_id} ({summary})")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/integration/test_cli_runtime.py
git commit -m "feat(runtime): install command (params, pre-flight, build+verify, record)"
```

---

### Task E4: `llm runtime uninstall <id>`

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/integration/test_cli_runtime.py
def test_runtime_uninstall_removes_marker_only(tmp_path: Path):
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (runtimes_dir / "rt-a" / "leftover").write_text("keep me", encoding="utf-8")

    result = runner.invoke(app, ["runtime", "uninstall", "rt-a", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0
    assert not (runtimes_dir / "rt-a" / ".installed").exists()
    assert (runtimes_dir / "rt-a" / "leftover").exists()


def test_runtime_uninstall_purge_removes_tree(tmp_path: Path):
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (runtimes_dir / "rt-a" / "leftover").write_text("bye", encoding="utf-8")

    result = runner.invoke(
        app, ["runtime", "uninstall", "rt-a", "--purge", "--yes"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert not (runtimes_dir / "rt-a").exists()


def test_runtime_uninstall_not_installed(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["runtime", "uninstall", "llamacpp", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "nothing to uninstall" in result.stdout.lower() or "not installed" in result.stdout.lower()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/commands/runtime_cmd.py
import shutil

from llm_cli.core.install_record import clear_record


@runtime_app.command("uninstall", help="Remove a runtime's install marker (and optionally artifacts).")
def runtime_uninstall(
    runtime_id: str = typer.Argument(...),
    purge: bool = typer.Option(False, "--purge", help="Also delete the install directory."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompts."),
) -> None:
    repo = repo_root()
    settings = _settings()
    runtime_dir = settings.runtimes_dir / runtime_id

    if not is_installed(settings.runtimes_dir, runtime_id):
        console.print(f"[yellow]nothing to uninstall:[/yellow] {runtime_id} is not installed")
        if not purge or not runtime_dir.exists():
            return

    if not yes:
        msg = (
            f"Purge {runtime_dir}? (all build artifacts will be deleted)"
            if purge
            else f"Remove install marker for {runtime_id}?"
        )
        if not typer.confirm(msg, default=False):
            console.print("aborted")
            raise typer.Exit(code=1)

    clear_record(settings.runtimes_dir, runtime_id)
    if purge and runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    append_history(
        repo, {"action": "runtime-uninstall", "id": runtime_id, "purge": purge}
    )
    console.print(f"[green]uninstalled[/green] {runtime_id}" + (" (purged)" if purge else ""))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/integration/test_cli_runtime.py
git commit -m "feat(runtime): uninstall (marker by default, --purge wipes tree)"
```

---

### Task E5: `llm runtime rebuild <id>`

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Modify: `tests/integration/test_cli_runtime.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/integration/test_cli_runtime.py
@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_rebuild_reuses_params(mock_verify, mock_build, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (tmp_path / "data" / "runtimes" / "llamacpp").mkdir(parents=True)

    runner.invoke(app, ["runtime", "install", "llamacpp", "--yes", "--param", "flavor=cuda", "--param", "jobs=2"], catch_exceptions=False)
    mock_build.reset_mock()
    result = runner.invoke(app, ["runtime", "rebuild", "llamacpp"], catch_exceptions=False)
    assert result.exit_code == 0
    env = mock_build.call_args.kwargs["env"]
    assert env["LLM_BUILD_FLAVOR"] == "cuda"
    assert env["LLM_BUILD_JOBS"] == "2"


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_rebuild_reset_reprompts_via_yes_defaults(mock_verify, mock_build, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (tmp_path / "data" / "runtimes" / "llamacpp").mkdir(parents=True)

    runner.invoke(app, ["runtime", "install", "llamacpp", "--yes", "--param", "flavor=cuda"], catch_exceptions=False)
    result = runner.invoke(app, ["runtime", "rebuild", "llamacpp", "--reset", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "llamacpp")
    assert rec.build_params["flavor"] == "cpu"  # default reasserted by --yes
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/commands/runtime_cmd.py
@runtime_app.command("rebuild", help="Reinstall a runtime; reuse stored build params unless --reset.")
def runtime_rebuild(
    runtime_id: str = typer.Argument(...),
    reset: bool = typer.Option(False, "--reset", help="Discard stored params and re-prompt."),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Build param key=value (repeatable)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults; skip prompts."),
) -> None:
    settings = _settings()
    rec = read_record(settings.runtimes_dir, runtime_id)
    extra_flags: list[str] = list(param)
    if rec is not None and not reset:
        for k, v in rec.build_params.items():
            extra_flags.append(f"{k}={v}")
    # Clear marker then re-install (no purge — keep artifacts).
    clear_record(settings.runtimes_dir, runtime_id)
    runtime_install(runtime_id=runtime_id, param=extra_flags, yes=yes)
    from llm_cli.core.repo import repo_root as _rr
    append_history(
        _rr(), {"action": "runtime-rebuild", "id": runtime_id, "reset": reset}
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_runtime.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/runtime_cmd.py tests/integration/test_cli_runtime.py
git commit -m "feat(runtime): rebuild (reuse stored params; --reset re-prompts)"
```

---

## Phase F — `llm model` sub-app

### Task F1: `commands/model_cmd.py` with list / info / pull

**Files:**
- Create: `src/llm_cli/commands/model_cmd.py`
- Test: `tests/integration/test_cli_model.py`
- Modify: `src/llm_cli/main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_model.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _scaffold(repo: Path) -> None:
    md = repo / "models" / "md-a"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text(
        "id: md-a\ndisplay_name: M\nsource: { kind: huggingface, repo: foo/bar }\n",
        encoding="utf-8",
    )
    (md / "pull.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def test_model_list(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["model", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "md-a" in result.stdout


def test_model_info(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["model", "info", "md-a"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "md-a" in result.stdout
    assert "huggingface" in result.stdout


@patch("llm_cli.commands.model_cmd.run_repo_bash", return_value=0)
def test_model_pull_calls_run_repo_bash(mock_run, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["model", "pull", "md-a"], catch_exceptions=False)
    assert result.exit_code == 0
    assert mock_run.call_args[0][1] == "models/md-a/pull.sh"
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_cli_model.py -v`
Expected: FAIL (sub-app not registered).

- [ ] **Step 3: Implementation**

```python
# src/llm_cli/commands/model_cmd.py
"""`llm model` — list/info/pull model definitions."""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core import registry
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.wsl import run_repo_bash

console = Console()
model_app = typer.Typer(help="Manage models (list/info/pull).")


@model_app.command("list", help="List models discovered in the repo.")
def model_list(as_json: bool = typer.Option(False, "--json")) -> None:
    repo = repo_root()
    rows = [
        {
            "id": m.id,
            "display_name": str(m.manifest.get("display_name", m.id)),
            "source_kind": str((m.manifest.get("source") or {}).get("kind", "")),
        }
        for m in registry.discover_models(repo)
    ]
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    table = Table(title="Models")
    table.add_column("ID")
    table.add_column("Display")
    table.add_column("Source")
    for r in rows:
        table.add_row(r["id"], r["display_name"], r["source_kind"] or "-")
    console.print(table)


@model_app.command("info", help="Show a model's manifest details.")
def model_info(model_id: str = typer.Argument(...)) -> None:
    repo = repo_root()
    md = registry.get_model(repo, model_id)
    if md is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    console.print(f"[bold]{md.id}[/bold] — {md.manifest.get('display_name', md.id)}")
    src = md.manifest.get("source") or {}
    if src:
        for k, v in src.items():
            console.print(f"  source.{k}: {v}")
    if md.manifest.get("description"):
        console.print(f"description: {md.manifest['description']}")


@model_app.command("pull", help="Run models/<id>/pull.sh in WSL with LLM_* env injected.")
def model_pull(model_id: str = typer.Argument(...)) -> None:
    repo = repo_root()
    md = registry.get_model(repo, model_id)
    if md is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    rc = run_repo_bash(settings, f"models/{model_id}/pull.sh")
    if rc != 0:
        console.print(f"[red]pull failed[/red] (exit {rc})")
        raise typer.Exit(code=rc)
```

```python
# Modify src/llm_cli/main.py — add import + mount
from llm_cli.commands.model_cmd import model_app
# ... and below `app.add_typer(runtime_app, name="runtime")`:
app.add_typer(model_app, name="model")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/model_cmd.py src/llm_cli/main.py tests/integration/test_cli_model.py
git commit -m "feat(model): model_app sub-app (list/info/pull)"
```

---

## Phase G — Serve gate + serve.params env build

### Task G1: Build serve env from validated `serve.params`

**Files:**
- Modify: `src/llm_cli/commands/serve.py`
- Modify: `src/llm_cli/core/config_resolve.py`
- Modify: `tests/unit/test_config_resolve.py`
- Modify: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Add a failing unit test for env emission**

```python
# tests/unit/test_serve_env.py
from __future__ import annotations

from pathlib import Path

from llm_cli.core import registry
from llm_cli.core.params import parse_schema
from llm_cli.core.settings import Settings
from llm_cli.commands.serve import _serve_env_from_params


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        repo_root=tmp_path / "repo",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
    )


def test_serve_env_from_params_basic(tmp_path: Path):
    s = _settings(tmp_path)
    schema = parse_schema(
        {
            "gguf_path": {"type": "path", "required": True, "env": "LLM_LLAMACPP_GGUF"},
            "ctx": {"type": "int", "default": 8192, "env": "LLM_LLAMACPP_CTX"},
        }
    )
    cfg_data = {
        "id": "c1",
        "runtime": "llamacpp",
        "serve": {
            "host": "127.0.0.1",
            "port": 8080,
            "params": {
                "gguf_path": "${models_dir}/x.gguf",
                "ctx": 4096,
            },
        },
    }
    env = _serve_env_from_params(s, cfg_data, schema)
    assert env["LLM_SERVE_HOST"] == "127.0.0.1"
    assert env["LLM_SERVE_PORT"] == "8080"
    assert env["LLM_CONFIG_ID"] == "c1"
    assert env["LLM_LLAMACPP_CTX"] == "4096"
    assert env["LLM_LLAMACPP_GGUF"].endswith("/x.gguf")
    # path was expanded (no template token left)
    assert "${" not in env["LLM_LLAMACPP_GGUF"]
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_serve_env.py -v`
Expected: FAIL (helper not exported).

- [ ] **Step 3: Implementation in `serve.py`**

```python
# Modify src/llm_cli/commands/serve.py:
# Add at module top, near existing imports:
from llm_cli.core.params import (
    ParamSpec,
    ParamType,
    derive_env_name,
    expand_path,
    validate_params,
)


def _serve_env_from_params(
    settings: Settings, cfg_data: dict[str, Any], schema: list[ParamSpec]
) -> dict[str, str]:
    """Build the env dict for serve.sh from validated serve.params."""
    serve = cfg_data["serve"]
    raw_params = serve.get("params") or {}
    coerced, errors = validate_params(schema, raw_params)
    if errors:
        for e in errors:
            console.print(f"[red]error:[/red] {cfg_data.get('id')}: {e}")
        raise typer.Exit(code=1)

    env: dict[str, str] = {
        "LLM_DATA_ROOT": settings.data_root.as_posix(),
        "LLM_REPO_ROOT": settings.repo_root.as_posix(),
        "LLM_RUNTIMES": settings.runtimes_dir.as_posix(),
        "LLM_MODELS": settings.models_dir.as_posix(),
        "LLM_CACHE": settings.cache_dir.as_posix(),
        "LLM_CONFIG_ID": str(cfg_data["id"]),
        "LLM_SERVE_HOST": str(serve["host"]),
        "LLM_SERVE_PORT": str(serve["port"]),
    }
    runtime_id = str(cfg_data["runtime"])
    for spec in schema:
        if spec.key not in coerced:
            continue
        value = coerced[spec.key]
        if spec.type is ParamType.PATH:
            value = expand_path(str(value), settings)
        env[derive_env_name(spec, runtime_id=runtime_id)] = str(value)

    merged = os.environ.copy()
    merged.update(env)
    return merged
```

Then replace the existing `_serve_env(...)` call sites in `serve.py` to use `_serve_env_from_params` instead, fetching the schema from `registry.get_runtime_manifest(repo, cfg.data['runtime']).serve_schema`. Concretely, in `serve(...)`:

```python
# Replace these lines in serve.py:
#   cfg_resolved = resolve_config_for_display(cfg, settings)
#   cfg_for_env = registry.ConfigRecord(id=cfg.id, path=cfg.path, data=cfg_resolved)
#   env = _serve_env(settings, cfg_for_env.data)
# with:
mf = registry.get_runtime_manifest(repo, str(cfg.data["runtime"]))
if mf is None:
    console.print(f"[red]error:[/red] unknown runtime {cfg.data['runtime']!r}")
    raise typer.Exit(code=1)
cfg_for_env = registry.ConfigRecord(id=cfg.id, path=cfg.path, data=cfg.data)
env = _serve_env_from_params(settings, cfg_for_env.data, mf.serve_schema)
```

Apply the equivalent change inside `switch(...)`.

- [ ] **Step 4: Update the existing `tests/integration/test_cli_serve.py` so the fake config uses `serve.params` schema-compatible values**

(Read that file first to see the exact current shape; in general, replace `serve.env: { X: foo }` with `serve.params: { ... }` and add a matching `serve:` schema to the test runtime's manifest. Skip if the file already uses `params`.)

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_serve_env.py tests/integration/test_cli_serve.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/commands/serve.py tests/unit/test_serve_env.py tests/integration/test_cli_serve.py
git commit -m "feat(serve): build env from validated serve.params (replaces serve.env free-form)"
```

---

### Task G2: `.installed` gate before any serve

**Files:**
- Modify: `src/llm_cli/commands/serve.py`
- Modify: `tests/integration/test_cli_serve.py`

- [ ] **Step 1: Append failing test** and update the existing `_make_repo` helper so every other test in this file pre-writes `.installed` for `rt-a` (otherwise the new gate breaks all of them).

```python
# Modify the existing _make_repo in tests/integration/test_cli_serve.py
# 1) Make `.installed` opt-out via a parameter (default: write it).
def _make_repo(root: Path, port: int = 18080, *, installed: bool = True) -> Path:
    repo = root / "repo"
    repo.mkdir()
    rt = repo / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text("id: rt-a\n", encoding="utf-8")
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    md = repo / "models" / "md-a"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text("id: md-a\n", encoding="utf-8")
    (md / "pull.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (repo / "configs").mkdir()
    (repo / "configs" / "cfg-a.yaml").write_text(
        f"id: cfg-a\nruntime: rt-a\nmodel: md-a\nserve:\n  host: 127.0.0.1\n  port: {port}\n",
        encoding="utf-8",
    )
    if installed:
        from llm_cli.core.install_record import InstallRecord, write_record
        runtimes_dir = root / "data" / "runtimes"
        runtimes_dir.mkdir(parents=True, exist_ok=True)
        write_record(
            runtimes_dir,
            InstallRecord(
                runtime_id="rt-a",
                installed_at="2026-05-17T00:00:00Z",
                build_params={},
                build_sh_sha256="x",
                verify_passed=True,
                schema_hash="y",
            ),
        )
    return repo


def test_serve_refuses_when_runtime_uninstalled(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, port=18120, installed=False)
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["serve", "cfg-a"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "not installed" in result.stdout.lower()
    assert "llm runtime install" in result.stdout
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_cli_serve.py::test_serve_refuses_when_runtime_uninstalled -v`
Expected: FAIL.

- [ ] **Step 3: Implementation — insert the gate in `serve(...)` of `commands/serve.py`**

```python
# In src/llm_cli/commands/serve.py serve(...), insert right after
# `cfg = _resolve_cfg(repo, config_id)`:
from llm_cli.core.install_record import is_installed as _is_installed

if not _is_installed(settings.runtimes_dir, str(cfg.data["runtime"])):
    console.print(
        f"[red]error:[/red] runtime {cfg.data['runtime']!r} is not installed"
    )
    console.print(f"hint:  llm runtime install {cfg.data['runtime']}")
    raise typer.Exit(code=1)
```

(Note: `settings` is built a few lines later in current code; reorder so it's resolved before the gate, or call `resolve(load_settings())` inline for the gate. Pick whichever keeps the diff smallest.)

Add the same gate to `switch(...)` for the **new** config id (so a switch can't move us onto an uninstalled runtime).

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_serve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/serve.py tests/integration/test_cli_serve.py
git commit -m "feat(serve): refuse to start when runtime is not installed (with hint)"
```

---

## Phase H — Setup hint, sub-app wiring, drop top-level commands

### Task H1: Append "next steps" panel to `llm setup`

**Files:**
- Modify: `src/llm_cli/commands/setup.py`
- Modify: `tests/integration/test_cli_setup.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/integration/test_cli_setup.py
def test_setup_prints_next_steps_panel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from typer.testing import CliRunner

    from llm_cli.main import app

    result = CliRunner().invoke(app, ["setup", "--default"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Recommended next steps" in result.stdout
    assert "llm runtime install" in result.stdout
    assert "llm model pull" in result.stdout
    assert "llm serve" in result.stdout
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_cli_setup.py::test_setup_prints_next_steps_panel -v`
Expected: FAIL.

- [ ] **Step 3: Implementation**

```python
# Append to src/llm_cli/commands/setup.py, at the end of setup():
    console.print()
    console.print("[bold]Recommended next steps:[/bold]")
    console.print("  1. llm doctor                  # verify cross-cutting prereqs")
    console.print("  2. llm runtime list            # see available runtimes")
    console.print("  3. llm runtime install <id>    # install one (e.g. `llm runtime install llamacpp`)")
    console.print("  4. llm model list              # browse model definitions")
    console.print("  5. llm model pull <id>         # download weights")
    console.print("  6. llm config validate         # check launch configs")
    console.print("  7. llm serve <config-id>       # start a server")
```

- [ ] **Step 4: Run test**

Run: `pytest tests/integration/test_cli_setup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/setup.py tests/integration/test_cli_setup.py
git commit -m "feat(setup): print 'Recommended next steps' panel after settings save"
```

---

### Task H2: Remove top-level `llm build` / `llm pull`; delete `artifacts.py`

**Files:**
- Modify: `src/llm_cli/main.py`
- Delete: `src/llm_cli/commands/artifacts.py`
- Delete: `tests/integration/test_cli_milestone2.py` (legacy tests reference removed commands)
- Modify: `tests/integration/test_cli_help.py` to assert absence

- [ ] **Step 1: Append failing tests** (verify the new shape)

```python
# Append to tests/integration/test_cli_help.py
def test_top_level_build_pull_removed():
    from typer.testing import CliRunner

    from llm_cli.main import app

    runner = CliRunner()
    # `llm build x` should fail with usage error (unknown command).
    r1 = runner.invoke(app, ["build", "rt-a"])
    assert r1.exit_code != 0
    r2 = runner.invoke(app, ["pull", "md-a"])
    assert r2.exit_code != 0


def test_runtime_and_model_subapps_registered():
    from typer.testing import CliRunner

    from llm_cli.main import app

    runner = CliRunner()
    r1 = runner.invoke(app, ["runtime", "--help"])
    assert r1.exit_code == 0
    assert "install" in r1.stdout
    r2 = runner.invoke(app, ["model", "--help"])
    assert r2.exit_code == 0
    assert "pull" in r2.stdout
```

- [ ] **Step 2: Run tests** — verify the assertions fail today

Run: `pytest tests/integration/test_cli_help.py -v`
Expected: FAIL (build/pull still registered).

- [ ] **Step 3: Implementation**

In `src/llm_cli/main.py`, remove the two `app.command("build", ...)` and `app.command("pull", ...)` lines and the `from llm_cli.commands import ... artifacts ...` reference.

Delete:

```bash
git rm src/llm_cli/commands/artifacts.py
git rm tests/integration/test_cli_milestone2.py
```

(The functionality is replaced by `runtime install` + `model pull`; the milestone2 tests are about to be obsolete. Note: the new `test_cli_runtime.py` + `test_cli_model.py` cover the equivalent surface.)

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/main.py tests/integration/test_cli_help.py
git commit -m "feat(cli): remove top-level llm build/pull; runtime/model sub-apps are the surface"
```

---

## Phase I — Migrate existing runtimes & configs

### Task I1: Migrate `runtimes/stub-runtime`

**Files:**
- Modify: `runtimes/stub-runtime/manifest.yaml`
- Create: `runtimes/stub-runtime/verify.sh`

- [ ] **Step 1: Rewrite manifest**

```yaml
# runtimes/stub-runtime/manifest.yaml
id: stub-runtime
display_name: Stub Runtime (smoke)
official: true
description: >
  Minimal runtime package for exercising discovery, `llm runtime install`, and
  layout validation. Replace with a real inference server (vLLM, llama.cpp, …).
build: {}
serve: {}
```

- [ ] **Step 2: Add verify.sh**

```bash
# runtimes/stub-runtime/verify.sh
#!/usr/bin/env bash
set -euo pipefail
exit 0
```

- [ ] **Step 3: Validate locally**

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add runtimes/stub-runtime/manifest.yaml runtimes/stub-runtime/verify.sh
git commit -m "refactor(stub-runtime): adopt v2 manifest (empty build/serve schemas, official, verify.sh)"
```

---

### Task I2: Migrate `runtimes/llamacpp`

**Files:**
- Modify: `runtimes/llamacpp/manifest.yaml`
- Modify: `runtimes/llamacpp/build.sh`
- Create: `runtimes/llamacpp/verify.sh`

- [ ] **Step 1: Rewrite manifest**

```yaml
# runtimes/llamacpp/manifest.yaml
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

- [ ] **Step 2: Refactor build.sh to read LLM_BUILD_*** vars**

```bash
# runtimes/llamacpp/build.sh
#!/usr/bin/env bash
set -euo pipefail

: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set (eval \"\$(llm settings env)\")}"

ROOT="${LLM_RUNTIMES}/llamacpp"
SRC="${ROOT}/llama.cpp"
BUILD="${SRC}/build"

mkdir -p "${ROOT}"

if [[ ! -d "${SRC}/.git" ]]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "${SRC}"
fi

git -C "${SRC}" submodule update --init --recursive

FLAVOR="${LLM_BUILD_FLAVOR:-cuda}"
JOBS="${LLM_BUILD_JOBS:-0}"
if [[ "${JOBS}" -le 0 ]]; then
  JOBS="$(nproc 2>/dev/null || echo 4)"
fi

CMAKE_FLAGS=()
case "${FLAVOR}" in
  cuda)   CMAKE_FLAGS+=(-DGGML_CUDA=ON) ;;
  vulkan) CMAKE_FLAGS+=(-DGGML_VULKAN=ON) ;;
  cpu)    : ;;
  *) echo "error: unknown flavor ${FLAVOR}" >&2; exit 2 ;;
esac

cmake -S "${SRC}" -B "${BUILD}" -DCMAKE_BUILD_TYPE=Release "${CMAKE_FLAGS[@]}"
cmake --build "${BUILD}" --config Release -j"${JOBS}"

test -x "${BUILD}/bin/llama-server"
echo "llamacpp build: ok (flavor=${FLAVOR}, jobs=${JOBS})"
```

- [ ] **Step 3: Add verify.sh**

```bash
# runtimes/llamacpp/verify.sh
#!/usr/bin/env bash
set -euo pipefail
: "${LLM_RUNTIMES:?LLM_RUNTIMES must be set}"
BIN="${LLM_RUNTIMES}/llamacpp/llama.cpp/build/bin/llama-server"
if [[ ! -x "${BIN}" ]]; then
  echo "error: llama-server missing at ${BIN}" >&2
  exit 1
fi
"${BIN}" --version >/dev/null 2>&1 || "${BIN}" --help >/dev/null
```

- [ ] **Step 4: Run tests**

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtimes/llamacpp/manifest.yaml runtimes/llamacpp/build.sh runtimes/llamacpp/verify.sh
git commit -m "refactor(llamacpp): schema-driven manifest, LLM_BUILD_* contract, verify.sh"
```

---

### Task I3: Migrate the two existing configs to `serve.params`

**Files:**
- Modify: `configs/llamacpp__unsloth-qwen3.6-35b-a3b__default.yaml`
- Modify: `configs/stub-runtime__stub-model__default.yaml`

- [ ] **Step 1: Rewrite llamacpp config**

```yaml
# configs/llamacpp__unsloth-qwen3.6-35b-a3b__default.yaml
id: llamacpp__unsloth-qwen3.6-35b-a3b__default
runtime: llamacpp
model: unsloth-qwen3.6-35b-a3b
description: >
  llama-server + Unsloth Qwen3.6-35B-A3B MoE GGUF (default UD-Q4_K_XL).

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

- [ ] **Step 2: Rewrite stub config**

```yaml
# configs/stub-runtime__stub-model__default.yaml
id: stub-runtime__stub-model__default
runtime: stub-runtime
model: stub-model
serve:
  host: 127.0.0.1
  port: 18080
  params: {}
readiness:
  timeout_seconds: 120
```

(Note: previous `serve.env.STUB_MARK` is dropped — stub-runtime's serve.sh ignores it.)

- [ ] **Step 3: Run tests**

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 4: Validate with the CLI**

Run: `python -m llm_cli config validate`
Expected: both configs `ok` (warnings about runtimes being uninstalled are fine).

- [ ] **Step 5: Commit**

```bash
git add configs/llamacpp__unsloth-qwen3.6-35b-a3b__default.yaml configs/stub-runtime__stub-model__default.yaml
git commit -m "refactor(configs): use typed serve.params (replaces serve.env free-form)"
```

---

## Phase J — Docs

### Task J1: Rewrite `docs/add-a-runtime.md`

**Files:**
- Modify: `docs/add-a-runtime.md`

- [ ] **Step 1: Rewrite the file**

Replace the entire contents of `docs/add-a-runtime.md` with a HOWTO oriented around the new manifest schema. Cover:

1. Folder layout (`manifest.yaml`, `build.sh`, `verify.sh`, `serve.sh`, `healthcheck.sh`).
2. Manifest sections (`requires`, `build`, `serve`) with the full llamacpp example.
3. Param types and the `env:` field.
4. `when:` clauses for conditional deps.
5. Script contracts (env vars each receives; `LLM_BUILD_*` for build.sh; runtime-named for serve.sh).
6. Install flow (`llm runtime install <id>`), then `verify`, then `serve.params` validation in configs.
7. Verification commands (`llm runtime info`, `llm doctor --runtime <id>`, `llm config validate`, `llm serve`).
8. Cross-links to the spec, the lifecycle doc, and `docs/repo-conventions.md`.

- [ ] **Step 2: Commit**

```bash
git add docs/add-a-runtime.md
git commit -m "docs(add-a-runtime): rewrite for typed manifest, four-script contract, install flow"
```

---

### Task J2: Add `docs/runtime-lifecycle.md`

**Files:**
- Create: `docs/runtime-lifecycle.md`

- [ ] **Step 1: Write the file**

Cover:
1. The five runtime commands (`list`, `info`, `install`, `uninstall`, `rebuild`) with examples.
2. What the `.installed` record contains and where it lives.
3. Build params vs serve params: who picks what when.
4. Drift behavior (build.sh sha, schema_hash) — informational, fixed via `rebuild --reset`.
5. Pre-flight: `llm doctor --runtime <id>` semantics.
6. Why serve refuses to start without `.installed`.
7. Cross-links to spec + `docs/lifecycle.md`.

- [ ] **Step 2: Commit**

```bash
git add docs/runtime-lifecycle.md
git commit -m "docs(runtime-lifecycle): install/uninstall/rebuild, .installed, drift behavior"
```

---

### Task J3: Update `docs/add-a-model.md`, `docs/lifecycle.md`, `README.md`, old spec note

**Files:**
- Modify: `docs/add-a-model.md`
- Modify: `docs/lifecycle.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`

- [ ] **Step 1: Updates**

- `docs/add-a-model.md`: replace `llm pull <id>` with `llm model pull <id>`. Add a note: "Model parameter schema is a follow-up spec — for now, pull.sh keeps its free-form env contract."
- `docs/lifecycle.md`: in the pre-serve section, add a line: "Before any spawn, the CLI checks `${runtimes_dir}/<runtime-id>/.installed`. If absent, serve refuses with hint `llm runtime install <id>`."
- `README.md`: replace `llm build` / `llm pull` rows in the CLI table with `llm runtime [list|info|install|uninstall|rebuild]` and `llm model [list|info|pull]`. Update the Getting Started snippet to: `llm setup` → `llm runtime install llamacpp` → `llm model pull unsloth-qwen3.6-35b-a3b` → `llm config validate` → `llm serve llamacpp__unsloth-qwen3.6-35b-a3b__default`.
- Old design spec (`2026-05-15-localllm-scaffolding-design.md`): add a third "Updated …" note at the top pointing at this new spec, similar to the existing notes for settings and lifecycle.

- [ ] **Step 2: Run tests** (no test impact expected; sanity check)

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add docs/add-a-model.md docs/lifecycle.md README.md docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md
git commit -m "docs: sweep for runtime/model sub-apps and .installed serve gate"
```

---

## Final task: full sweep + plan close-out

### Task Z1: Final sweep and `requirements.md` regen

**Files:** all

- [ ] **Step 1: Run the whole suite**

Run: `pytest tests -q`
Expected: PASS (skips for Windows-only / systemd-only are fine).

- [ ] **Step 2: Regenerate `requirements.md`**

Run: `python -m llm_cli doctor render-requirements`
Verify the file now contains a `## Universal` section and `## Runtime: llamacpp` section.

- [ ] **Step 3: Commit the regenerated docs**

```bash
git add requirements.md
git commit -m "docs(requirements): regenerate with universal + per-runtime sections"
```

- [ ] **Step 4: Sanity-test the CLI manually inside WSL**

```bash
llm setup --default
llm runtime list
llm runtime install stub-runtime --yes
llm runtime info stub-runtime
llm config validate
llm serve stub-runtime__stub-model__default
llm status
llm stop
llm runtime uninstall stub-runtime --yes
```

Expected: each command succeeds (serve is the existing toy TCP listener, healthcheck passes within a couple of seconds).

- [ ] **Step 5: Tag and close**

```bash
git log --oneline | head -20
```

Confirm a clean chain of small commits per task.

---

## Spec coverage cross-check

| Spec section | Covered by |
|---|---|
| §5.1 Runtime manifest, schema | A1–A6, C1, I1, I2 |
| §5.1.1 Param types | A1, A2, A3 |
| §5.1.2 `when:` clauses | A5, D1, D2 |
| §5.1.3 Path templating | A3 |
| §5.1.4 Provenance (`official`) | C1, E1, I1, I2 |
| §5.2 Script contract (`verify.sh`) | E3, I1, I2 |
| §5.3 Install record (`.installed`) | B1, B2, E3 |
| §5.4 Config shape + validation | C2, G1, I3 |
| §5.5 CLI surface | E1–E5, F1, H2 |
| §5.5.1 Install flow | E3 |
| §5.5.2 Uninstall (`--purge`) | E4 |
| §5.5.3 Rebuild | E5 |
| §5.5.4 Info + drift | E2 |
| §5.6 `.installed` gate in serve | G2 |
| §5.7 Setup hint | H1 |
| §5.8 Requirements integration | D1, D2, D3, D4 |
| §6 Module layout | All phases |
| §7 Testing | All phases (every task includes tests) |
| §8 Documentation | J1, J2, J3, Z1 |
