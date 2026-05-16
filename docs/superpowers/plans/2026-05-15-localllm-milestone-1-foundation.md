# LocalLLM Milestone 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the LocalLLM repo with the Python CLI skeleton, `llm init`, `llm specs`, and `llm doctor`. After this milestone, you can document your machine to `specs.md` and verify external prerequisites against `requirements.yaml`/`requirements.md`.

**Architecture:** A Python package `llm_cli` (src layout), Typer-based CLI with a console-script entrypoint registered via `pyproject.toml`. Core modules under `llm_cli/core/` hold the testable logic (paths, version comparison, hardware detection, requirements checks); per-command modules under `llm_cli/commands/` are thin Typer wrappers.

**Tech Stack:** Python 3.11+, Typer (CLI), PyYAML (config), httpx (later milestones), Rich (output), pytest + pytest-mock (tests), Hatch (build backend), pip editable install via `install.sh`.

**Spec deviation flagged:** the spec lists `scripts/llm` and `scripts/_*.py`. The implementation uses `src/llm_cli/` with a console-script entrypoint instead — same external API (`llm` on PATH after install), better Python packaging idiom, easier to test. The repo will not have a `scripts/` directory; `install.sh` lives at the repo root.

**Reference spec:** `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`

---

## File Structure (locked at start of milestone)

Created during this milestone:

```
LocalLLM/
├── README.md                              # Task 17
├── .gitignore                             # Task 1
├── paths.yaml                             # Task 1
├── requirements.yaml                      # Task 11
├── requirements.md                        # Task 13 (auto-generated, committed)
├── pyproject.toml                         # Task 2
├── install.sh                             # Task 15
│
├── runtimes/.gitkeep                      # Task 1
├── models/.gitkeep                        # Task 1
├── configs/.gitkeep                       # Task 1
├── benchmarks/.gitkeep                    # Task 1
├── state/.gitkeep                         # Task 1
│
├── src/
│   └── llm_cli/
│       ├── __init__.py                    # Task 2
│       ├── __main__.py                    # Task 2
│       ├── main.py                        # Task 2; extended in Tasks 6, 10, 14
│       ├── core/
│       │   ├── __init__.py                # Task 2
│       │   ├── paths.py                   # Task 3
│       │   ├── versions.py                # Task 4
│       │   ├── shell.py                   # Task 5
│       │   ├── specs.py                   # Tasks 7, 8, 9
│       │   └── doctor.py                  # Tasks 12, 13
│       └── commands/
│           ├── __init__.py                # Task 2
│           ├── init.py                    # Task 6
│           ├── specs.py                   # Task 10
│           └── doctor.py                  # Task 14
│
├── tests/
│   ├── __init__.py                        # Task 2
│   ├── conftest.py                        # Task 2
│   ├── unit/
│   │   ├── __init__.py                    # Task 2
│   │   ├── test_paths.py                  # Task 3
│   │   ├── test_versions.py               # Task 4
│   │   ├── test_shell.py                  # Task 5
│   │   ├── test_specs_detect.py           # Task 7
│   │   ├── test_specs_render.py           # Task 8
│   │   ├── test_specs_marker.py           # Task 9
│   │   ├── test_doctor_check.py           # Task 12
│   │   └── test_doctor_render.py          # Task 13
│   └── integration/
│       ├── __init__.py                    # Task 2
│       ├── test_cli_help.py               # Task 2
│       ├── test_cli_init.py               # Task 6
│       ├── test_cli_specs.py              # Task 10
│       └── test_cli_doctor.py             # Task 14
│
└── docs/
    ├── README.md                          # Task 17
    └── wsl-setup.md                       # Task 17
```

Already exists:
- `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`
- `docs/superpowers/plans/2026-05-15-localllm-milestone-1-foundation.md` (this file)
- `.git/`

---

## Task 1: Repo skeleton — directories, gitignore, paths.yaml

**Files:**
- Create: `.gitignore`
- Create: `paths.yaml`
- Create: `runtimes/.gitkeep`, `models/.gitkeep`, `configs/.gitkeep`, `benchmarks/.gitkeep`, `state/.gitkeep`

No tests for this task — it's pure scaffolding. The next task verifies the structure works.

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.pytest_cache/
.venv/
venv/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# LocalLLM runtime state (machine-local, not committed)
state/running.json
state/history.jsonl
state/logs/
.llm-env

# Per-spec gitignore: large benchmark artifacts opt-out
benchmarks/*/results/**/raw/_large/

# Build artifacts
build/
dist/
*.egg
```

- [ ] **Step 2: Create `paths.yaml`**

```yaml
# Single source of truth for where LLM data lives in WSL.
# Edit and re-run `llm init` to relocate.

data_root: ~/llm
runtimes: ${data_root}/runtimes
models:   ${data_root}/models
cache:    ${data_root}/cache
```

- [ ] **Step 3: Create directory placeholders**

Create empty `.gitkeep` files in `runtimes/`, `models/`, `configs/`, `benchmarks/`, `state/`. On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path runtimes,models,configs,benchmarks,state | Out-Null
"" | Out-File -Encoding ascii runtimes/.gitkeep,models/.gitkeep,configs/.gitkeep,benchmarks/.gitkeep,state/.gitkeep
```

- [ ] **Step 4: Commit**

```
git add .gitignore paths.yaml runtimes/.gitkeep models/.gitkeep configs/.gitkeep benchmarks/.gitkeep state/.gitkeep
git commit -F-
```

Commit message:

```
chore: add repo skeleton (gitignore, paths.yaml, dir placeholders)

Establishes the top-level layout per the design spec. paths.yaml is the
single source of truth for WSL data locations.
```

---

## Task 2: Python package skeleton + first failing CLI test

**Files:**
- Create: `pyproject.toml`
- Create: `src/llm_cli/__init__.py`, `src/llm_cli/__main__.py`, `src/llm_cli/main.py`
- Create: `src/llm_cli/core/__init__.py`, `src/llm_cli/commands/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- Create: `tests/integration/test_cli_help.py`

This task establishes the package and proves the CLI is invokable.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "localllm-cli"
version = "0.1.0"
description = "Personal control plane for local LLM runtimes"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12,<1.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "rich>=13.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
]

[project.scripts]
llm = "llm_cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/llm_cli"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
```

- [ ] **Step 2: Create empty package files**

```python
# src/llm_cli/__init__.py
__version__ = "0.1.0"
```

```python
# src/llm_cli/__main__.py
from llm_cli.main import app

if __name__ == "__main__":
    app()
```

```python
# src/llm_cli/core/__init__.py
```

```python
# src/llm_cli/commands/__init__.py
```

```python
# tests/__init__.py
```

```python
# tests/unit/__init__.py
```

```python
# tests/integration/__init__.py
```

```python
# tests/conftest.py
import sys
from pathlib import Path

# Make src/ importable in tests without requiring an editable install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
```

- [ ] **Step 3: Write the failing CLI smoke test**

```python
# tests/integration/test_cli_help.py
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_help_shows_program_name():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "llm" in result.stdout.lower()


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout
```

- [ ] **Step 4: Install dev deps in a venv and run the failing test**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest tests/integration/test_cli_help.py -v
```

Expected: failure — `ModuleNotFoundError: No module named 'llm_cli.main'` (or import error inside main.py since it's empty).

- [ ] **Step 5: Implement minimal `main.py`**

```python
# src/llm_cli/main.py
"""LocalLLM CLI entrypoint."""
from typing import Optional

import typer

from llm_cli import __version__

app = typer.Typer(
    name="llm",
    help="LocalLLM — control plane for local LLM runtimes.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llm {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """LocalLLM CLI — manage runtimes, models, configs, and benchmarks."""
```

- [ ] **Step 6: Run the test to verify it passes**

```powershell
pytest tests/integration/test_cli_help.py -v
```

Expected: both tests PASS.

- [ ] **Step 7: Commit**

```
git add pyproject.toml src/ tests/
git commit -F-
```

Commit message:

```
feat: add Python package skeleton and CLI smoke test

src/llm_cli/ package with Typer app, pyproject.toml registering the `llm`
console script, and a smoke test that exercises --help and --version.
```

---

## Task 3: `paths.py` — load and resolve `paths.yaml`

**Files:**
- Create: `src/llm_cli/core/paths.py`
- Create: `tests/unit/test_paths.py`

`paths.yaml` uses `${data_root}` substitution. We need to load it, expand `~`, and resolve the variable references.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_paths.py
from pathlib import Path

import pytest

from llm_cli.core.paths import Paths, load_paths


def test_load_paths_expands_tilde_and_substitutes(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: ~/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    paths = load_paths(yaml_file)

    home = Path.home()
    assert paths.data_root == home / "llm"
    assert paths.runtimes == home / "llm" / "runtimes"
    assert paths.models == home / "llm" / "models"
    assert paths.cache == home / "llm" / "cache"


def test_load_paths_supports_absolute_data_root(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: /opt/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    paths = load_paths(yaml_file)

    assert paths.data_root == Path("/opt/llm")
    assert paths.runtimes == Path("/opt/llm/runtimes")


def test_load_paths_missing_required_key_raises(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text("data_root: ~/llm\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required key"):
        load_paths(yaml_file)


def test_load_paths_unresolved_variable_raises(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: ~/llm\n"
        "runtimes: ${not_a_real_var}/x\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved variable"):
        load_paths(yaml_file)


def test_paths_to_env_dict_returns_uppercased_strings(tmp_path: Path) -> None:
    yaml_file = tmp_path / "paths.yaml"
    yaml_file.write_text(
        "data_root: /opt/llm\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )
    paths = load_paths(yaml_file)

    env = paths.to_env_dict()

    assert env == {
        "LLM_DATA_ROOT": "/opt/llm",
        "LLM_RUNTIMES": "/opt/llm/runtimes",
        "LLM_MODELS": "/opt/llm/models",
        "LLM_CACHE": "/opt/llm/cache",
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_paths.py -v
```

Expected: ImportError (module doesn't exist).

- [ ] **Step 3: Implement `paths.py`**

```python
# src/llm_cli/core/paths.py
"""Load and resolve paths.yaml — the single source of truth for WSL data locations."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REQUIRED_KEYS = ("data_root", "runtimes", "models", "cache")
_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class Paths:
    data_root: Path
    runtimes: Path
    models: Path
    cache: Path

    def to_env_dict(self) -> dict[str, str]:
        """Render as LLM_* env vars for shell scripts to source."""
        return {
            "LLM_DATA_ROOT": str(self.data_root),
            "LLM_RUNTIMES": str(self.runtimes),
            "LLM_MODELS": str(self.models),
            "LLM_CACHE": str(self.cache),
        }


def _substitute(value: str, scope: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in scope:
            raise ValueError(f"unresolved variable ${{{key}}}")
        return scope[key]

    return _VAR_RE.sub(repl, value)


def load_paths(path: Path) -> Paths:
    """Load and resolve paths.yaml, expanding ~ and ${var} references.

    Resolution is single-pass with `data_root` available as the only variable.
    This is deliberately simple — paths.yaml is short and has no need for
    arbitrary nesting.
    """
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    for key in REQUIRED_KEYS:
        if key not in raw:
            raise ValueError(f"paths.yaml missing required key: {key!r}")

    data_root_raw = str(raw["data_root"])
    data_root = Path(data_root_raw).expanduser()

    scope = {"data_root": str(data_root)}
    resolved: dict[str, Path] = {"data_root": data_root}
    for key in ("runtimes", "models", "cache"):
        substituted = _substitute(str(raw[key]), scope)
        resolved[key] = Path(substituted).expanduser()

    return Paths(**resolved)
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_paths.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/paths.py tests/unit/test_paths.py
git commit -F-
```

Commit message:

```
feat(core): add Paths loader for paths.yaml

Loads paths.yaml, expands ~, resolves ${data_root} substitutions, and
exposes a Paths dataclass. to_env_dict() renders the LLM_* env vars
that shell scripts will source.
```

---

## Task 4: `versions.py` — version comparison helper

**Files:**
- Create: `src/llm_cli/core/versions.py`
- Create: `tests/unit/test_versions.py`

The doctor needs to compare detected versions like `560.94.07` against minimums like `535.0`. Stdlib `packaging.version` would work but is a heavy dependency for a tiny need. Implement a simple tuple-of-ints comparison.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_versions.py
import pytest

from llm_cli.core.versions import compare_versions, parse_version


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("560.94", (560, 94)),
        ("3.11", (3, 11)),
        ("0.20.0", (0, 20, 0)),
        ("12.6", (12, 6)),
        ("v1.2.3", (1, 2, 3)),  # leading 'v' tolerated
    ],
)
def test_parse_version_extracts_numeric_tuple(raw: str, expected: tuple[int, ...]) -> None:
    assert parse_version(raw) == expected


def test_parse_version_handles_prerelease_suffix() -> None:
    assert parse_version("11.4.0-rc1") == (11, 4, 0)


def test_parse_version_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_version("not-a-version")


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("1.2.3", "1.2.3", 0),
        ("1.2.3", "1.2.4", -1),
        ("1.3", "1.2.99", 1),
        ("560.94", "535.0", 1),
        ("3.11", "3.11.0", 0),  # missing components treated as 0
        ("3.10", "3.11", -1),
    ],
)
def test_compare_versions(a: str, b: str, expected: int) -> None:
    assert compare_versions(a, b) == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_versions.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `versions.py`**

```python
# src/llm_cli/core/versions.py
"""Lightweight version parsing and comparison.

Avoids depending on `packaging` for a tiny subset of needs.
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"\d+")


def parse_version(raw: str) -> tuple[int, ...]:
    """Extract numeric components from a version-like string.

    Strips leading 'v' and any non-numeric suffix (e.g. '-rc1').
    Raises ValueError if no numeric components found.
    """
    text = raw.strip().lstrip("v")
    parts = _NUM_RE.findall(text)
    if not parts:
        raise ValueError(f"no numeric components in version string: {raw!r}")
    return tuple(int(p) for p in parts)


def compare_versions(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b.

    Missing components are treated as 0, so '3.11' == '3.11.0'.
    """
    pa = parse_version(a)
    pb = parse_version(b)
    length = max(len(pa), len(pb))
    pa_padded = pa + (0,) * (length - len(pa))
    pb_padded = pb + (0,) * (length - len(pb))
    if pa_padded < pb_padded:
        return -1
    if pa_padded > pb_padded:
        return 1
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_versions.py -v
```

Expected: all 9 parameterized cases PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/versions.py tests/unit/test_versions.py
git commit -F-
```

Commit message:

```
feat(core): add lightweight version parser and comparator

parse_version tolerates 'v' prefix and trailing pre-release tags;
compare_versions pads missing components with 0.
```

---

## Task 5: `shell.py` — subprocess helper

**Files:**
- Create: `src/llm_cli/core/shell.py`
- Create: `tests/unit/test_shell.py`

A small wrapper around `subprocess.run` that captures stdout+stderr, applies a timeout, and returns a structured result. Used by `_specs.py` and `_doctor.py` to invoke `nvidia-smi`, `lscpu`, etc.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_shell.py
import sys

import pytest

from llm_cli.core.shell import CommandResult, run_command


def test_run_command_captures_stdout() -> None:
    result = run_command([sys.executable, "-c", "print('hello')"])
    assert isinstance(result, CommandResult)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.stderr == ""
    assert result.found is True


def test_run_command_captures_nonzero_exit() -> None:
    result = run_command([sys.executable, "-c", "import sys; sys.exit(2)"])
    assert result.exit_code == 2
    assert result.found is True


def test_run_command_missing_executable_returns_not_found() -> None:
    result = run_command(["__definitely_not_a_command_42__"])
    assert result.found is False
    assert result.exit_code == -1


def test_run_command_timeout_returns_timeout_flag() -> None:
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_sec=0.5,
    )
    assert result.timed_out is True
    assert result.found is True


def test_run_command_passes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_command(
        [sys.executable, "-c", "import os; print(os.environ.get('FOO', 'unset'))"],
        env={"FOO": "bar"},
    )
    assert "bar" in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_shell.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `shell.py`**

```python
# src/llm_cli/core/shell.py
"""Thin subprocess wrapper used by detection and check helpers."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    found: bool       # False if executable not on PATH
    timed_out: bool   # True if killed by timeout


def run_command(
    cmd: Sequence[str],
    *,
    timeout_sec: float = 10.0,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> CommandResult:
    """Run a command, capture its output, never raise on failure.

    Returns CommandResult with `found=False` if the executable isn't on PATH
    and `timed_out=True` if the process was killed by the timeout.
    """
    full_env: dict[str, str] = dict(os.environ)
    if env:
        full_env.update(env)

    try:
        completed = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=full_env,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(exit_code=-1, stdout="", stderr="", found=False, timed_out=False)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            exit_code=-1,
            stdout=exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "",
            stderr=exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "",
            found=True,
            timed_out=True,
        )

    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        found=True,
        timed_out=False,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_shell.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/shell.py tests/unit/test_shell.py
git commit -F-
```

Commit message:

```
feat(core): add run_command subprocess helper

CommandResult captures exit code, stdout, stderr, plus structured flags
for not-found and timed-out cases. Never raises on subprocess failure;
callers branch on the result.
```

---

## Task 6: `llm init` command

**Files:**
- Create: `src/llm_cli/commands/init.py`
- Modify: `src/llm_cli/main.py` (register command)
- Create: `tests/integration/test_cli_init.py`

`llm init` reads `paths.yaml`, creates the `$LLM_DATA_ROOT/{runtimes,models,cache}` directories, and writes a resolved `.llm-env` at the repo root for shell scripts to source.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_init.py
from pathlib import Path

from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _write_paths(repo: Path, data_root: Path) -> None:
    (repo / "paths.yaml").write_text(
        f"data_root: {data_root}\n"
        "runtimes: ${data_root}/runtimes\n"
        "models: ${data_root}/models\n"
        "cache: ${data_root}/cache\n",
        encoding="utf-8",
    )


def test_init_creates_data_root_dirs_and_env_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data_root = tmp_path / "data"
    _write_paths(repo, data_root)

    result = runner.invoke(app, ["init"], catch_exceptions=False, env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0, result.stdout
    assert (data_root / "runtimes").is_dir()
    assert (data_root / "models").is_dir()
    assert (data_root / "cache").is_dir()

    env_file = repo / ".llm-env"
    assert env_file.is_file()
    contents = env_file.read_text(encoding="utf-8")
    assert f"LLM_DATA_ROOT={data_root}" in contents
    assert f"LLM_RUNTIMES={data_root / 'runtimes'}" in contents
    assert f"LLM_MODELS={data_root / 'models'}" in contents
    assert f"LLM_CACHE={data_root / 'cache'}" in contents


def test_init_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data_root = tmp_path / "data"
    _write_paths(repo, data_root)

    runner.invoke(app, ["init"], env={"LLM_REPO_ROOT": str(repo)})
    result = runner.invoke(app, ["init"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0
    assert (data_root / "runtimes").is_dir()


def test_init_missing_paths_yaml_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    result = runner.invoke(app, ["init"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code != 0
    assert "paths.yaml" in result.stdout or "paths.yaml" in (result.stderr or "")
```

- [ ] **Step 2: Run the test to verify it fails**

```powershell
pytest tests/integration/test_cli_init.py -v
```

Expected: failure — `init` command doesn't exist (Typer error: "No such command 'init'").

- [ ] **Step 3: Implement `commands/init.py`**

```python
# src/llm_cli/commands/init.py
"""`llm init` — read paths.yaml, create data root layout, write .llm-env."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.paths import load_paths

console = Console()


def _repo_root() -> Path:
    """Locate the repo root.

    Tests inject LLM_REPO_ROOT; otherwise we fall back to the CWD. Later
    milestones may add a more sophisticated discovery (walk up looking for
    paths.yaml).
    """
    explicit = os.environ.get("LLM_REPO_ROOT")
    if explicit:
        return Path(explicit)
    return Path.cwd()


def init() -> None:
    """Read paths.yaml, create data-root subdirectories, write .llm-env."""
    repo = _repo_root()
    paths_yaml = repo / "paths.yaml"
    if not paths_yaml.is_file():
        console.print(f"[red]error:[/red] paths.yaml not found at {paths_yaml}")
        raise typer.Exit(code=1)

    paths = load_paths(paths_yaml)

    for target in (paths.data_root, paths.runtimes, paths.models, paths.cache):
        target.mkdir(parents=True, exist_ok=True)

    env_file = repo / ".llm-env"
    lines = [f"{k}={v}" for k, v in paths.to_env_dict().items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    console.print(f"[green]initialized[/green] data root at {paths.data_root}")
    console.print(f"[green]wrote[/green] {env_file}")
```

- [ ] **Step 4: Wire into `main.py`**

Modify `src/llm_cli/main.py` — add the import and registration. The new file:

```python
# src/llm_cli/main.py
"""LocalLLM CLI entrypoint."""
from typing import Optional

import typer

from llm_cli import __version__
from llm_cli.commands import init as init_cmd

app = typer.Typer(
    name="llm",
    help="LocalLLM — control plane for local LLM runtimes.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llm {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """LocalLLM CLI — manage runtimes, models, configs, and benchmarks."""


app.command("init", help="Read paths.yaml, create data-root dirs, write .llm-env.")(init_cmd.init)
```

- [ ] **Step 5: Run the tests to verify they pass**

```powershell
pytest tests/integration/test_cli_init.py tests/integration/test_cli_help.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/llm_cli/commands/init.py src/llm_cli/main.py tests/integration/test_cli_init.py
git commit -F-
```

Commit message:

```
feat(cli): add `llm init` command

Reads paths.yaml, creates the data-root subdirectories, writes a resolved
.llm-env file at the repo root. Idempotent. Resolves repo root from
LLM_REPO_ROOT env var with CWD fallback.
```

---

## Task 7: `specs.py` core — hardware/env detection

**Files:**
- Create: `src/llm_cli/core/specs.py` (detection only)
- Create: `tests/unit/test_specs_detect.py`

Detection functions take an `executor` callable so tests can swap in fakes. Each function returns a structured result (dataclass) and degrades gracefully when the underlying tool is missing.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_specs_detect.py
from __future__ import annotations

from dataclasses import dataclass

import pytest

from llm_cli.core.shell import CommandResult
from llm_cli.core.specs import (
    CpuInfo,
    GpuInfo,
    OsInfo,
    WslInfo,
    detect_cpu,
    detect_gpus,
    detect_os,
    detect_ram_gb,
    detect_wsl,
    parse_meminfo_total_kb,
    parse_nvidia_smi_csv,
    parse_proc_cpuinfo,
)


SAMPLE_CPUINFO = """\
processor\t: 0
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 9 7950X 16-Core Processor
cpu MHz\t\t: 4500.000
cache size\t: 1024 KB

processor\t: 1
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 9 7950X 16-Core Processor
cpu MHz\t\t: 4500.000
"""


SAMPLE_NVIDIA_SMI_CSV = """\
0, NVIDIA GeForce RTX 4090, 24564 MiB, 560.94
1, NVIDIA GeForce RTX 4090, 24564 MiB, 560.94
"""


def test_parse_proc_cpuinfo_extracts_model_and_count() -> None:
    info = parse_proc_cpuinfo(SAMPLE_CPUINFO)
    assert info.model == "AMD Ryzen 9 7950X 16-Core Processor"
    assert info.logical_cores == 2  # the sample has 2 entries


def test_parse_proc_cpuinfo_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_proc_cpuinfo("")


def test_parse_meminfo_total_kb() -> None:
    sample = (
        "MemTotal:       65816184 kB\n"
        "MemFree:         1234567 kB\n"
        "MemAvailable:   45678901 kB\n"
    )
    assert parse_meminfo_total_kb(sample) == 65816184


def test_parse_nvidia_smi_csv() -> None:
    gpus = parse_nvidia_smi_csv(SAMPLE_NVIDIA_SMI_CSV)
    assert len(gpus) == 2
    assert gpus[0] == GpuInfo(index=0, name="NVIDIA GeForce RTX 4090", vram_gb=24, driver="560.94")
    assert gpus[1].index == 1


def test_parse_nvidia_smi_csv_empty_returns_empty_list() -> None:
    assert parse_nvidia_smi_csv("") == []


def test_detect_cpu_uses_executor(tmp_path) -> None:
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(SAMPLE_CPUINFO, encoding="utf-8")

    info = detect_cpu(read_text=lambda p: cpuinfo.read_text(encoding="utf-8"))

    assert info.model.startswith("AMD Ryzen 9 7950X")
    assert info.logical_cores == 2


def test_detect_ram_gb(tmp_path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       65816184 kB\n", encoding="utf-8")

    ram_gb = detect_ram_gb(read_text=lambda p: meminfo.read_text(encoding="utf-8"))

    # 65816184 kB / 1024 / 1024 ≈ 62.77 GB; round to 63
    assert 60 <= ram_gb <= 70


def test_detect_gpus_returns_empty_when_smi_missing() -> None:
    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=-1, stdout="", stderr="", found=False, timed_out=False
    )
    assert detect_gpus(run_command=fake_run) == []


def test_detect_gpus_parses_csv_when_smi_present() -> None:
    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=0, stdout=SAMPLE_NVIDIA_SMI_CSV, stderr="", found=True, timed_out=False
    )
    gpus = detect_gpus(run_command=fake_run)
    assert len(gpus) == 2


def test_detect_os_via_cmd_exe() -> None:
    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=0,
        stdout="\nMicrosoft Windows [Version 10.0.22631.4111]\n",
        stderr="",
        found=True,
        timed_out=False,
    )
    info = detect_os(run_command=fake_run)
    assert "Windows" in info.description
    assert "22631" in info.description


def test_detect_wsl_reads_distro_and_kernel(tmp_path) -> None:
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="Ubuntu"\nVERSION_ID="22.04"\nPRETTY_NAME="Ubuntu 22.04.4 LTS"\n',
        encoding="utf-8",
    )

    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=0,
        stdout="5.15.153.1-microsoft-standard-WSL2\n",
        stderr="",
        found=True,
        timed_out=False,
    )

    info = detect_wsl(
        read_text=lambda p: os_release.read_text(encoding="utf-8"),
        run_command=fake_run,
    )
    assert "Ubuntu 22.04" in info.distro
    assert "microsoft-standard-WSL2" in info.kernel
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_specs_detect.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `specs.py` (detection portion only)**

```python
# src/llm_cli/core/specs.py
"""Hardware and environment detection for `llm specs`.

Detection functions accept injected `read_text` and `run_command` callables
so tests can substitute fakes. Each detector degrades gracefully — missing
tools yield "not detected" markers instead of exceptions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from llm_cli.core.shell import CommandResult, run_command as _real_run_command

NOT_DETECTED = "not detected"

ReadText = Callable[[Path | str], str]
RunCommand = Callable[..., CommandResult]


def _default_read_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


@dataclass(frozen=True)
class CpuInfo:
    model: str
    logical_cores: int


@dataclass(frozen=True)
class GpuInfo:
    index: int
    name: str
    vram_gb: int
    driver: str


@dataclass(frozen=True)
class OsInfo:
    description: str


@dataclass(frozen=True)
class WslInfo:
    distro: str
    kernel: str


@dataclass(frozen=True)
class SystemSpecs:
    cpu: CpuInfo
    ram_gb: int
    gpus: list[GpuInfo] = field(default_factory=list)
    cuda_runtime: str = NOT_DETECTED
    os: OsInfo = OsInfo(description=NOT_DETECTED)
    wsl: WslInfo = WslInfo(distro=NOT_DETECTED, kernel=NOT_DETECTED)
    systemd_enabled: bool = False
    repo_root: str = NOT_DETECTED
    data_root: str = NOT_DETECTED


# ---------- parsers (pure functions over strings) ----------

def parse_proc_cpuinfo(text: str) -> CpuInfo:
    if not text.strip():
        raise ValueError("empty /proc/cpuinfo")

    model_match = re.search(r"^model name\s*:\s*(.+)$", text, re.MULTILINE)
    if not model_match:
        raise ValueError("model name not found in /proc/cpuinfo")
    model = model_match.group(1).strip()

    logical_cores = len(re.findall(r"^processor\s*:", text, re.MULTILINE))
    return CpuInfo(model=model, logical_cores=logical_cores)


def parse_meminfo_total_kb(text: str) -> int:
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.MULTILINE)
    if not match:
        raise ValueError("MemTotal not found in /proc/meminfo")
    return int(match.group(1))


def parse_nvidia_smi_csv(text: str) -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        idx_s, name, vram_s, driver = parts[0], parts[1], parts[2], parts[3]
        try:
            idx = int(idx_s)
        except ValueError:
            continue
        vram_match = re.search(r"(\d+)", vram_s)
        if not vram_match:
            continue
        vram_mib = int(vram_match.group(1))
        vram_gb = round(vram_mib / 1024)
        gpus.append(GpuInfo(index=idx, name=name, vram_gb=vram_gb, driver=driver))
    return gpus


# ---------- detectors (use injected IO) ----------

def detect_cpu(read_text: ReadText = _default_read_text) -> CpuInfo:
    try:
        return parse_proc_cpuinfo(read_text("/proc/cpuinfo"))
    except (FileNotFoundError, ValueError):
        return CpuInfo(model=NOT_DETECTED, logical_cores=0)


def detect_ram_gb(read_text: ReadText = _default_read_text) -> int:
    try:
        kb = parse_meminfo_total_kb(read_text("/proc/meminfo"))
        return round(kb / 1024 / 1024)
    except (FileNotFoundError, ValueError):
        return 0


def detect_gpus(run_command: RunCommand = _real_run_command) -> list[GpuInfo]:
    result = run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,driver_version",
            "--format=csv,noheader",
        ],
        timeout_sec=5.0,
    )
    if not result.found or result.exit_code != 0:
        return []
    return parse_nvidia_smi_csv(result.stdout)


def detect_cuda_runtime(run_command: RunCommand = _real_run_command) -> str:
    """Best-effort CUDA runtime version from `nvidia-smi`."""
    result = run_command(["nvidia-smi"], timeout_sec=5.0)
    if not result.found or result.exit_code != 0:
        return NOT_DETECTED
    match = re.search(r"CUDA Version:\s*([\d.]+)", result.stdout)
    return match.group(1) if match else NOT_DETECTED


def detect_os(run_command: RunCommand = _real_run_command) -> OsInfo:
    """Read Windows version via WSL interop (`cmd.exe /c ver`)."""
    result = run_command(["cmd.exe", "/c", "ver"], timeout_sec=5.0)
    if not result.found or result.exit_code != 0:
        return OsInfo(description=NOT_DETECTED)
    description = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else NOT_DETECTED
    return OsInfo(description=description)


def detect_wsl(
    read_text: ReadText = _default_read_text,
    run_command: RunCommand = _real_run_command,
) -> WslInfo:
    distro = NOT_DETECTED
    try:
        os_release = read_text("/etc/os-release")
        match = re.search(r'^PRETTY_NAME="?(.+?)"?$', os_release, re.MULTILINE)
        if match:
            distro = match.group(1).strip()
    except FileNotFoundError:
        pass

    kernel = NOT_DETECTED
    result = run_command(["uname", "-r"], timeout_sec=2.0)
    if result.found and result.exit_code == 0:
        kernel = result.stdout.strip()

    return WslInfo(distro=distro, kernel=kernel)


def detect_systemd(
    read_text: ReadText = _default_read_text,
    run_command: RunCommand = _real_run_command,
) -> bool:
    """Return True if WSL has systemd enabled."""
    try:
        wsl_conf = read_text("/etc/wsl.conf")
        if re.search(r"^\s*systemd\s*=\s*true", wsl_conf, re.MULTILINE | re.IGNORECASE):
            result = run_command(["systemctl", "is-system-running"], timeout_sec=3.0)
            return result.found and result.exit_code in (0, 1)  # 1 = degraded; still systemd
    except FileNotFoundError:
        pass
    return False


def detect_all(
    read_text: ReadText = _default_read_text,
    run_command: RunCommand = _real_run_command,
    *,
    repo_root: str = NOT_DETECTED,
    data_root: str = NOT_DETECTED,
) -> SystemSpecs:
    """Collect everything detectable into a SystemSpecs."""
    return SystemSpecs(
        cpu=detect_cpu(read_text),
        ram_gb=detect_ram_gb(read_text),
        gpus=detect_gpus(run_command),
        cuda_runtime=detect_cuda_runtime(run_command),
        os=detect_os(run_command),
        wsl=detect_wsl(read_text, run_command),
        systemd_enabled=detect_systemd(read_text, run_command),
        repo_root=repo_root,
        data_root=data_root,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_specs_detect.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/specs.py tests/unit/test_specs_detect.py
git commit -F-
```

Commit message:

```
feat(core): add hardware/env detection for llm specs

CPU, RAM, GPU, CUDA, OS, WSL distro/kernel, and systemd-enabled detection.
Each detector accepts injected IO so tests use fakes; missing tools
degrade to NOT_DETECTED rather than raising.
```

---

## Task 8: `specs.py` rendering — SystemSpecs → Markdown

**Files:**
- Modify: `src/llm_cli/core/specs.py` (append rendering)
- Create: `tests/unit/test_specs_render.py`

Rendering produces just the inner block — no markers, no title, no notes section. The marker logic lives in Task 9.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_specs_render.py
from llm_cli.core.specs import (
    CpuInfo,
    GpuInfo,
    OsInfo,
    SystemSpecs,
    WslInfo,
    render_specs_block,
)


def _example_specs() -> SystemSpecs:
    return SystemSpecs(
        cpu=CpuInfo(model="AMD Ryzen 9 7950X 16-Core Processor", logical_cores=32),
        ram_gb=64,
        gpus=[GpuInfo(index=0, name="NVIDIA GeForce RTX 4090", vram_gb=24, driver="560.94")],
        cuda_runtime="12.6",
        os=OsInfo(description="Microsoft Windows [Version 10.0.22631.4111]"),
        wsl=WslInfo(distro="Ubuntu 22.04.4 LTS", kernel="5.15.153.1-microsoft-standard-WSL2"),
        systemd_enabled=True,
        repo_root="/mnt/c/Private/Projects/LocalLLM",
        data_root="/home/melih/llm",
    )


def test_render_specs_block_contains_all_sections() -> None:
    md = render_specs_block(_example_specs(), generated_at="2026-05-15T18:30:00Z")
    assert "_Generated: 2026-05-15T18:30:00Z_" in md
    assert "## Host" in md
    assert "AMD Ryzen 9 7950X" in md
    assert "64 GB" in md
    assert "## GPU" in md
    assert "RTX 4090" in md
    assert "560.94" in md
    assert "CUDA runtime: 12.6" in md
    assert "## WSL" in md
    assert "Ubuntu 22.04" in md
    assert "microsoft-standard-WSL2" in md
    assert "Systemd:** enabled" in md
    assert "## Storage layout" in md
    assert "/mnt/c/Private/Projects/LocalLLM" in md
    assert "/home/melih/llm" in md


def test_render_specs_block_no_gpu_falls_back_gracefully() -> None:
    specs = SystemSpecs(
        cpu=CpuInfo(model="cpu", logical_cores=1),
        ram_gb=8,
    )
    md = render_specs_block(specs, generated_at="2026-05-15T18:30:00Z")
    assert "## GPU" in md
    assert "no GPU detected" in md.lower()


def test_render_specs_block_systemd_disabled_label() -> None:
    specs = SystemSpecs(
        cpu=CpuInfo(model="cpu", logical_cores=1),
        ram_gb=8,
        wsl=WslInfo(distro="Ubuntu", kernel="x"),
        systemd_enabled=False,
    )
    md = render_specs_block(specs, generated_at="2026-05-15T18:30:00Z")
    assert "Systemd:** disabled" in md
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_specs_render.py -v
```

Expected: ImportError.

- [ ] **Step 3: Add rendering functions to `specs.py`**

Append to `src/llm_cli/core/specs.py`:

```python
# ---------- rendering ----------

def render_specs_block(specs: SystemSpecs, *, generated_at: str) -> str:
    """Render the inner specs block (no surrounding markers, no notes section)."""
    lines: list[str] = []
    lines.append(f"_Generated: {generated_at}_")
    lines.append("")
    lines.append("## Host")
    lines.append(f"- **OS:** {specs.os.description}")
    lines.append(f"- **CPU:** {specs.cpu.model} ({specs.cpu.logical_cores} logical cores)")
    lines.append(f"- **RAM:** {specs.ram_gb} GB")
    lines.append("")
    lines.append("## GPU")
    if specs.gpus:
        lines.append("| Idx | Name | VRAM | Driver |")
        lines.append("|---|---|---|---|")
        for gpu in specs.gpus:
            lines.append(f"| {gpu.index} | {gpu.name} | {gpu.vram_gb} GB | {gpu.driver} |")
    else:
        lines.append("_No GPU detected._")
    lines.append("")
    lines.append(f"CUDA runtime: {specs.cuda_runtime}")
    lines.append("")
    lines.append("## WSL")
    lines.append(f"- **Distro:** {specs.wsl.distro}")
    lines.append(f"- **Kernel:** {specs.wsl.kernel}")
    systemd_label = "enabled" if specs.systemd_enabled else "disabled"
    lines.append(f"- **Systemd:** {systemd_label}")
    lines.append("")
    lines.append("## Storage layout")
    lines.append(f"- Repo: `{specs.repo_root}`")
    lines.append(f"- Data root: `{specs.data_root}`")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_specs_render.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/specs.py tests/unit/test_specs_render.py
git commit -F-
```

Commit message:

```
feat(core): render SystemSpecs to a Markdown block

render_specs_block produces the inner block (host/GPU/WSL/storage) with
graceful fallbacks for missing GPU and a systemd enabled/disabled label.
```

---

## Task 9: `specs.py` marker logic — preserve notes regions

**Files:**
- Modify: `src/llm_cli/core/specs.py` (append marker handling)
- Create: `tests/unit/test_specs_marker.py`

The auto block lives between `<!-- llm:specs:start -->` and `<!-- llm:specs:end -->`. Everything outside these markers is preserved verbatim. If markers are missing, refuse to write unless `force=True`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_specs_marker.py
import pytest

from llm_cli.core.specs import (
    SPECS_END_MARKER,
    SPECS_START_MARKER,
    MarkersMissingError,
    update_specs_markdown,
)


SCAFFOLD = f"""\
# System Specs

<!-- AUTO-GENERATED: do not edit between markers. Run `llm specs` to regenerate. -->
{SPECS_START_MARKER}
OLD CONTENT
{SPECS_END_MARKER}

## Notes
- BIOS: foo
- Power plan: bar
"""


def test_update_replaces_only_between_markers() -> None:
    new_block = "_Generated: 2026-05-15T00:00:00Z_\n\n## Host\n- **CPU:** test"
    result = update_specs_markdown(SCAFFOLD, new_block)

    assert "OLD CONTENT" not in result
    assert "## Notes" in result
    assert "BIOS: foo" in result
    assert "_Generated: 2026-05-15T00:00:00Z_" in result
    assert SPECS_START_MARKER in result
    assert SPECS_END_MARKER in result


def test_update_missing_markers_raises_unless_forced() -> None:
    no_markers = "# System Specs\n\n## Notes\nfoo\n"
    with pytest.raises(MarkersMissingError):
        update_specs_markdown(no_markers, "new block")

    forced = update_specs_markdown(no_markers, "new block", force=True)
    assert SPECS_START_MARKER in forced
    assert SPECS_END_MARKER in forced
    assert "new block" in forced


def test_update_preserves_leading_content() -> None:
    text = (
        "# Specs\n\n"
        "Some intro paragraph.\n\n"
        f"{SPECS_START_MARKER}\nOLD\n{SPECS_END_MARKER}\n\n"
        "## Notes\nstuff\n"
    )
    result = update_specs_markdown(text, "NEW")
    assert "Some intro paragraph." in result
    assert "OLD" not in result
    assert "NEW" in result


def test_update_idempotent_for_same_block() -> None:
    block = "fresh content"
    once = update_specs_markdown(SCAFFOLD, block)
    twice = update_specs_markdown(once, block)
    assert once == twice
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_specs_marker.py -v
```

Expected: ImportError.

- [ ] **Step 3: Append marker handling to `specs.py`**

Append to `src/llm_cli/core/specs.py`:

```python
# ---------- marker handling ----------

SPECS_START_MARKER = "<!-- llm:specs:start -->"
SPECS_END_MARKER = "<!-- llm:specs:end -->"

_AUTOGEN_HEADER_COMMENT = (
    "<!-- AUTO-GENERATED: do not edit between markers. "
    "Run `llm specs` to regenerate. -->"
)


class MarkersMissingError(RuntimeError):
    """Raised when specs.md does not contain the expected markers."""


def _scaffold_with_markers(block: str) -> str:
    return (
        "# System Specs\n\n"
        f"{_AUTOGEN_HEADER_COMMENT}\n"
        f"{SPECS_START_MARKER}\n"
        f"{block}\n"
        f"{SPECS_END_MARKER}\n\n"
        "## Notes\n"
        "<!-- Free-form. Preserved across regenerations. -->\n"
    )


def update_specs_markdown(existing: str, new_block: str, *, force: bool = False) -> str:
    """Replace the contents between markers with new_block.

    Returns the updated text. Raises MarkersMissingError if markers are
    missing and force=False; if force=True, replaces the entire file with
    a scaffold containing the new block.
    """
    start_idx = existing.find(SPECS_START_MARKER)
    end_idx = existing.find(SPECS_END_MARKER)

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        if not force:
            raise MarkersMissingError(
                "specs.md is missing the llm:specs markers; pass force=True to overwrite."
            )
        return _scaffold_with_markers(new_block)

    head = existing[: start_idx + len(SPECS_START_MARKER)]
    tail = existing[end_idx:]
    return f"{head}\n{new_block}\n{tail}"
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_specs_marker.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/specs.py tests/unit/test_specs_marker.py
git commit -F-
```

Commit message:

```
feat(core): preserve notes when updating specs.md

update_specs_markdown rewrites only the bytes between the llm:specs
markers; everything outside (notes, intro paragraphs) is preserved.
Missing markers raise MarkersMissingError unless force=True.
```

---

## Task 10: `llm specs` command

**Files:**
- Create: `src/llm_cli/commands/specs.py`
- Modify: `src/llm_cli/main.py` (register command)
- Create: `tests/integration/test_cli_specs.py`

`llm specs` regenerates the auto block in `specs.md`. Flags: `--check` exits nonzero on drift, `--print` prints detection without touching the file.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_cli_specs.py
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.core.specs import (
    SPECS_END_MARKER,
    SPECS_START_MARKER,
    CpuInfo,
    OsInfo,
    SystemSpecs,
    WslInfo,
)
from llm_cli.main import app

runner = CliRunner()


def _fake_specs() -> SystemSpecs:
    return SystemSpecs(
        cpu=CpuInfo(model="Test CPU", logical_cores=4),
        ram_gb=16,
        gpus=[],
        cuda_runtime="not detected",
        os=OsInfo(description="Test OS"),
        wsl=WslInfo(distro="Ubuntu Test", kernel="x.y.z"),
        systemd_enabled=True,
        repo_root="/test/repo",
        data_root="/test/data",
    )


@pytest.fixture
def patch_detect_all(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "llm_cli.commands.specs.detect_all",
        lambda *a, **kw: _fake_specs(),
    )


def _write_paths(repo: Path, data_root: Path) -> None:
    (repo / "paths.yaml").write_text(
        f"data_root: {data_root}\nruntimes: ${{data_root}}/runtimes\n"
        f"models: ${{data_root}}/models\ncache: ${{data_root}}/cache\n",
        encoding="utf-8",
    )


def test_specs_creates_scaffold_when_file_missing(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")

    result = runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0, result.stdout
    specs_md = repo / "specs.md"
    assert specs_md.is_file()
    contents = specs_md.read_text(encoding="utf-8")
    assert SPECS_START_MARKER in contents
    assert SPECS_END_MARKER in contents
    assert "Test CPU" in contents
    assert "## Notes" in contents


def test_specs_preserves_notes_section(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")
    (repo / "specs.md").write_text(
        f"# System Specs\n\n{SPECS_START_MARKER}\nOLD\n{SPECS_END_MARKER}\n\n"
        "## Notes\n- preserved line\n",
        encoding="utf-8",
    )

    runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})

    contents = (repo / "specs.md").read_text(encoding="utf-8")
    assert "preserved line" in contents
    assert "OLD" not in contents
    assert "Test CPU" in contents


def test_specs_print_does_not_touch_file(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")

    result = runner.invoke(app, ["specs", "--print"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0
    assert "Test CPU" in result.stdout
    assert not (repo / "specs.md").exists()


def test_specs_check_clean_exits_zero(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")

    runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})  # establish baseline
    result = runner.invoke(app, ["specs", "--check"], env={"LLM_REPO_ROOT": str(repo)})

    # Detection is identical, so the auto block matches; exit 0.
    assert result.exit_code == 0


def test_specs_check_drift_exits_nonzero(tmp_path: Path, monkeypatch, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")
    runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})

    drifted = SystemSpecs(
        cpu=CpuInfo(model="DIFFERENT CPU", logical_cores=8),
        ram_gb=32,
    )
    monkeypatch.setattr("llm_cli.commands.specs.detect_all", lambda *a, **kw: drifted)

    result = runner.invoke(app, ["specs", "--check"], env={"LLM_REPO_ROOT": str(repo)})
    assert result.exit_code != 0
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/integration/test_cli_specs.py -v
```

Expected: failure — `specs` command doesn't exist.

- [ ] **Step 3: Implement `commands/specs.py`**

```python
# src/llm_cli/commands/specs.py
"""`llm specs` — regenerate the auto block in specs.md."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.paths import load_paths
from llm_cli.core.specs import (
    MarkersMissingError,
    detect_all,
    render_specs_block,
    update_specs_markdown,
)

console = Console()


def _repo_root() -> Path:
    explicit = os.environ.get("LLM_REPO_ROOT")
    return Path(explicit) if explicit else Path.cwd()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gather_block(repo: Path) -> str:
    paths_yaml = repo / "paths.yaml"
    data_root = "not detected"
    if paths_yaml.is_file():
        try:
            data_root = str(load_paths(paths_yaml).data_root)
        except Exception:
            pass
    specs = detect_all(repo_root=str(repo), data_root=data_root)
    return render_specs_block(specs, generated_at=_utcnow_iso())


def specs_command(
    check: bool = typer.Option(
        False, "--check", help="Compare detection against specs.md; exit nonzero on drift."
    ),
    print_only: bool = typer.Option(
        False, "--print", help="Print detection result without writing specs.md."
    ),
    force: bool = typer.Option(
        False, "--force", help="Recreate specs.md from scratch if markers are missing."
    ),
) -> None:
    """Regenerate the auto block in specs.md."""
    repo = _repo_root()
    new_block = _gather_block(repo)

    if print_only:
        typer.echo(new_block)
        raise typer.Exit(code=0)

    specs_md = repo / "specs.md"

    if check:
        if not specs_md.is_file():
            console.print("[red]drift:[/red] specs.md does not exist")
            raise typer.Exit(code=2)
        current = specs_md.read_text(encoding="utf-8")
        try:
            updated = update_specs_markdown(current, new_block)
        except MarkersMissingError:
            console.print("[red]drift:[/red] specs.md is missing markers")
            raise typer.Exit(code=2)
        # Compare ignoring the _Generated: line so timestamps don't trigger drift.
        def _strip_timestamp(text: str) -> str:
            return "\n".join(
                line for line in text.splitlines() if not line.startswith("_Generated:")
            )
        if _strip_timestamp(current) == _strip_timestamp(updated):
            console.print("[green]ok:[/green] specs.md matches detected specs")
            raise typer.Exit(code=0)
        console.print("[yellow]drift:[/yellow] specs.md does not match detected specs")
        raise typer.Exit(code=1)

    existing = specs_md.read_text(encoding="utf-8") if specs_md.is_file() else ""
    try:
        new_text = update_specs_markdown(existing or "", new_block, force=force or not existing)
    except MarkersMissingError:
        console.print("[red]error:[/red] specs.md is missing the llm:specs markers (use --force to recreate)")
        raise typer.Exit(code=1)

    specs_md.write_text(new_text, encoding="utf-8")
    console.print(f"[green]wrote[/green] {specs_md}")
```

- [ ] **Step 4: Wire into `main.py`**

Modify `src/llm_cli/main.py` to add the registration line. The full updated file:

```python
# src/llm_cli/main.py
"""LocalLLM CLI entrypoint."""
from typing import Optional

import typer

from llm_cli import __version__
from llm_cli.commands import init as init_cmd
from llm_cli.commands import specs as specs_cmd

app = typer.Typer(
    name="llm",
    help="LocalLLM — control plane for local LLM runtimes.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llm {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """LocalLLM CLI — manage runtimes, models, configs, and benchmarks."""


app.command("init", help="Read paths.yaml, create data-root dirs, write .llm-env.")(init_cmd.init)
app.command("specs", help="Regenerate the auto block in specs.md.")(specs_cmd.specs_command)
```

- [ ] **Step 5: Run the tests to verify they pass**

```powershell
pytest tests/integration/test_cli_specs.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/llm_cli/commands/specs.py src/llm_cli/main.py tests/integration/test_cli_specs.py
git commit -F-
```

Commit message:

```
feat(cli): add `llm specs` command

Regenerates the llm:specs auto block in specs.md, preserving the Notes
section and any other content outside markers. --check exits nonzero on
drift; --print emits detection without writing.
```

---

## Task 11: Initial `requirements.yaml`

**Files:**
- Create: `requirements.yaml`

This task seeds `requirements.yaml` with the cross-cutting external prerequisites identified in the spec. No code, no tests — pure data file.

- [ ] **Step 1: Create `requirements.yaml`**

```yaml
# Cross-cutting external prerequisites for the LocalLLM repo.
# Source of truth — `requirements.md` is auto-generated from this file.
# Add a new entry with: id, name, why, verify (cmd + version_regex + min), install_hint.

- id: cuda-driver
  name: NVIDIA CUDA Driver (Windows host)
  why: GPU passthrough into WSL2
  verify:
    cmd: nvidia-smi
    version_regex: 'Driver Version:\s*([\d.]+)'
    min: "535.0"
  install_hint: "https://www.nvidia.com/Download/index.aspx"

- id: python
  name: Python
  why: Base interpreter for runtime venvs and the CLI
  verify:
    cmd: python3 --version
    version_regex: 'Python\s+([\d.]+)'
    min: "3.11"
  install_hint: "apt install python3.11 python3.11-venv"

- id: hf-cli
  name: huggingface-hub CLI
  why: Used by models/*/pull.sh to fetch weights
  verify:
    cmd: huggingface-cli --version
    version_regex: '([\d.]+)'
    min: "0.20.0"
  install_hint: "pip install -U huggingface_hub[cli]"

- id: build-essential
  name: build-essential + cmake
  why: Building llama.cpp and similar native runtimes
  verify:
    cmd: gcc --version
    version_regex: 'gcc.*?([\d.]+)'
    min: "11.0"
  install_hint: "apt install build-essential cmake"

- id: git
  name: Git
  why: Cloning runtime forks in runtimes/*/build.sh
  verify:
    cmd: git --version
    version_regex: 'git version\s+([\d.]+)'
    min: "2.30"
  install_hint: "apt install git"

- id: curl
  name: curl
  why: healthcheck.sh and ad-hoc endpoint probing
  verify:
    cmd: curl --version
    version_regex: 'curl\s+([\d.]+)'
    min: "7.80"
  install_hint: "apt install curl"

- id: jq
  name: jq
  why: JSON parsing in shell scripts
  verify:
    cmd: jq --version
    version_regex: 'jq-([\d.]+)'
    min: "1.6"
  install_hint: "apt install jq"
```

- [ ] **Step 2: Commit**

```
git add requirements.yaml
git commit -F-
```

Commit message:

```
feat: seed requirements.yaml with cross-cutting prerequisites

Lists CUDA driver, Python, hf CLI, build tools, git, curl, jq. Each entry
has verify (cmd + regex + min) and install_hint. requirements.md is
generated from this file in a later task.
```

---

## Task 12: `doctor.py` — requirement check execution

**Files:**
- Create: `src/llm_cli/core/doctor.py`
- Create: `tests/unit/test_doctor_check.py`

Loads `requirements.yaml`, runs each `verify.cmd`, extracts a version with `version_regex`, compares against `min` using `versions.compare_versions`. Returns structured results.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_doctor_check.py
from pathlib import Path

from llm_cli.core.doctor import (
    CheckStatus,
    Requirement,
    RequirementResult,
    check_requirement,
    load_requirements,
)
from llm_cli.core.shell import CommandResult


def _ok_run(stdout: str):
    return lambda cmd, **kw: CommandResult(
        exit_code=0, stdout=stdout, stderr="", found=True, timed_out=False
    )


def _missing_run():
    return lambda cmd, **kw: CommandResult(
        exit_code=-1, stdout="", stderr="", found=False, timed_out=False
    )


def _example_req() -> Requirement:
    return Requirement(
        id="python",
        name="Python",
        why="for tests",
        verify_cmd="python3 --version",
        version_regex=r"Python\s+([\d.]+)",
        min_version="3.11",
        install_hint="apt install python3.11",
    )


def test_check_requirement_ok() -> None:
    result = check_requirement(_example_req(), run_command=_ok_run("Python 3.11.9\n"))
    assert isinstance(result, RequirementResult)
    assert result.status == CheckStatus.OK
    assert result.detected_version == "3.11.9"


def test_check_requirement_too_old() -> None:
    result = check_requirement(_example_req(), run_command=_ok_run("Python 3.10.6\n"))
    assert result.status == CheckStatus.OUTDATED
    assert result.detected_version == "3.10.6"


def test_check_requirement_missing_executable() -> None:
    result = check_requirement(_example_req(), run_command=_missing_run())
    assert result.status == CheckStatus.MISSING
    assert result.detected_version is None


def test_check_requirement_unparseable_output_marks_unknown() -> None:
    result = check_requirement(_example_req(), run_command=_ok_run("garbage\n"))
    assert result.status == CheckStatus.UNKNOWN


def test_check_requirement_no_min_marks_ok_when_present() -> None:
    req = Requirement(
        id="x", name="x", why="x",
        verify_cmd="echo hi",
        version_regex=r"hi",
        min_version=None,
        install_hint="",
    )
    result = check_requirement(req, run_command=_ok_run("hi\n"))
    assert result.status == CheckStatus.OK


def test_load_requirements_parses_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "requirements.yaml"
    yaml_file.write_text(
        "- id: python\n"
        "  name: Python\n"
        "  why: base interpreter\n"
        "  verify:\n"
        "    cmd: python3 --version\n"
        "    version_regex: 'Python\\s+([\\d.]+)'\n"
        "    min: '3.11'\n"
        "  install_hint: 'apt install python3.11'\n",
        encoding="utf-8",
    )

    reqs = load_requirements(yaml_file)
    assert len(reqs) == 1
    assert reqs[0].id == "python"
    assert reqs[0].min_version == "3.11"
    assert reqs[0].verify_cmd == "python3 --version"
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_doctor_check.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `doctor.py` (check portion only)**

```python
# src/llm_cli/core/doctor.py
"""Load requirements.yaml and execute checks."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

import yaml

from llm_cli.core.shell import CommandResult, run_command as _real_run_command
from llm_cli.core.versions import compare_versions

RunCommand = Callable[..., CommandResult]


class CheckStatus(str, Enum):
    OK = "ok"
    OUTDATED = "outdated"
    MISSING = "missing"
    UNKNOWN = "unknown"          # cmd ran but version couldn't be parsed
    ERROR = "error"              # cmd ran with nonzero exit


@dataclass(frozen=True)
class Requirement:
    id: str
    name: str
    why: str
    verify_cmd: str
    version_regex: str
    min_version: str | None
    install_hint: str


@dataclass(frozen=True)
class RequirementResult:
    requirement: Requirement
    status: CheckStatus
    detected_version: str | None = None
    detail: str = ""


def load_requirements(path: Path) -> list[Requirement]:
    """Load requirements.yaml into a list of Requirement objects."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError("requirements.yaml must be a top-level list")

    out: list[Requirement] = []
    for entry in raw:
        verify = entry.get("verify", {})
        out.append(
            Requirement(
                id=entry["id"],
                name=entry["name"],
                why=entry.get("why", ""),
                verify_cmd=verify["cmd"],
                version_regex=verify["version_regex"],
                min_version=verify.get("min"),
                install_hint=entry.get("install_hint", ""),
            )
        )
    return out


def check_requirement(
    req: Requirement,
    *,
    run_command: RunCommand = _real_run_command,
) -> RequirementResult:
    """Execute a single requirement's verify command and classify the result."""
    cmd_parts = shlex.split(req.verify_cmd)
    result = run_command(cmd_parts, timeout_sec=8.0)

    if not result.found:
        return RequirementResult(
            requirement=req, status=CheckStatus.MISSING, detail="executable not on PATH"
        )

    if result.exit_code != 0:
        return RequirementResult(
            requirement=req,
            status=CheckStatus.ERROR,
            detail=f"exit {result.exit_code}: {result.stderr.strip() or result.stdout.strip()}",
        )

    combined = result.stdout + "\n" + result.stderr
    match = re.search(req.version_regex, combined)
    if not match:
        return RequirementResult(
            requirement=req,
            status=CheckStatus.UNKNOWN,
            detail="version_regex did not match command output",
        )

    detected = match.group(1)

    if req.min_version is None:
        return RequirementResult(
            requirement=req, status=CheckStatus.OK, detected_version=detected
        )

    cmp = compare_versions(detected, req.min_version)
    if cmp >= 0:
        return RequirementResult(
            requirement=req, status=CheckStatus.OK, detected_version=detected
        )
    return RequirementResult(
        requirement=req,
        status=CheckStatus.OUTDATED,
        detected_version=detected,
        detail=f"need >= {req.min_version}",
    )


def check_all(
    requirements: list[Requirement],
    *,
    run_command: RunCommand = _real_run_command,
) -> list[RequirementResult]:
    return [check_requirement(r, run_command=run_command) for r in requirements]
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_doctor_check.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/doctor.py tests/unit/test_doctor_check.py
git commit -F-
```

Commit message:

```
feat(core): add requirement check execution

load_requirements parses requirements.yaml; check_requirement runs the
verify command, extracts a version with the configured regex, and
classifies the result as OK/OUTDATED/MISSING/UNKNOWN/ERROR.
```

---

## Task 13: `doctor.py` rendering — requirements.yaml → requirements.md

**Files:**
- Modify: `src/llm_cli/core/doctor.py` (append rendering)
- Create: `tests/unit/test_doctor_render.py`

Render `requirements.yaml` to a Markdown table with: ID, Name, Min Version, Verify Command, Install Hint, Why. The doctor also renders the *check results* in the CLI; this rendering is for the static `requirements.md` documentation file.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_doctor_render.py
from llm_cli.core.doctor import Requirement, render_requirements_md


def test_render_requirements_md_contains_table_headers_and_rows() -> None:
    reqs = [
        Requirement(
            id="python", name="Python", why="base interpreter",
            verify_cmd="python3 --version",
            version_regex=r"Python\s+([\d.]+)",
            min_version="3.11",
            install_hint="apt install python3.11",
        ),
        Requirement(
            id="git", name="Git", why="cloning runtime forks",
            verify_cmd="git --version",
            version_regex=r"git version\s+([\d.]+)",
            min_version=None,
            install_hint="apt install git",
        ),
    ]

    md = render_requirements_md(reqs)

    assert "# External Requirements" in md
    assert "auto-generated" in md.lower()
    assert "| ID | Name | Min | Verify | Install | Why |" in md
    assert "| python |" in md
    assert "Python" in md
    assert "3.11" in md
    assert "`python3 --version`" in md
    assert "apt install python3.11" in md
    assert "| git |" in md
    assert "—" in md  # min=None rendered as em dash
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/unit/test_doctor_render.py -v
```

Expected: ImportError on `render_requirements_md`.

- [ ] **Step 3: Append rendering to `doctor.py`**

Append to `src/llm_cli/core/doctor.py`:

```python
# ---------- requirements.md rendering ----------

_REQ_HEADER = (
    "# External Requirements\n\n"
    "<!-- AUTO-GENERATED from requirements.yaml — do not edit by hand. "
    "Run `llm doctor render-requirements` to regenerate. -->\n\n"
    "These prerequisites must exist on the machine for the LocalLLM CLI and the "
    "runtimes' build/serve scripts to function. Run `llm doctor` to verify the "
    "current state of each.\n\n"
)


def _escape_pipes(text: str) -> str:
    return text.replace("|", "\\|")


def render_requirements_md(requirements: list[Requirement]) -> str:
    """Render requirements.yaml to a Markdown table for human reading."""
    lines: list[str] = [_REQ_HEADER.rstrip(), ""]
    lines.append("| ID | Name | Min | Verify | Install | Why |")
    lines.append("|---|---|---|---|---|---|")
    for req in requirements:
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
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
pytest tests/unit/test_doctor_render.py -v
```

Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```
git add src/llm_cli/core/doctor.py tests/unit/test_doctor_render.py
git commit -F-
```

Commit message:

```
feat(core): render requirements.yaml to a Markdown table

render_requirements_md emits a single table (ID, Name, Min, Verify,
Install, Why) with an auto-generated header. Used by `llm doctor
render-requirements`.
```

---

## Task 14: `llm doctor` command + `render-requirements` subcommand

**Files:**
- Create: `src/llm_cli/commands/doctor.py`
- Modify: `src/llm_cli/main.py` (register command group)
- Create: `tests/integration/test_cli_doctor.py`

`llm doctor` prints a colored status table for each requirement and exits 0 if all OK, 1 otherwise. `llm doctor render-requirements` writes `requirements.md` from `requirements.yaml`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_cli_doctor.py
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.core.doctor import CheckStatus, Requirement, RequirementResult
from llm_cli.main import app

runner = CliRunner()


def _write_requirements(repo: Path) -> None:
    (repo / "requirements.yaml").write_text(
        "- id: python\n"
        "  name: Python\n"
        "  why: base\n"
        "  verify: { cmd: 'python3 --version', version_regex: 'Python\\s+([\\d.]+)', min: '3.11' }\n"
        "  install_hint: 'apt install python3.11'\n"
        "- id: git\n"
        "  name: Git\n"
        "  why: cloning\n"
        "  verify: { cmd: 'git --version', version_regex: 'git version\\s+([\\d.]+)' }\n"
        "  install_hint: 'apt install git'\n",
        encoding="utf-8",
    )


def test_doctor_render_requirements_writes_md(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)

    result = runner.invoke(
        app, ["doctor", "render-requirements"], env={"LLM_REPO_ROOT": str(repo)}
    )

    assert result.exit_code == 0, result.stdout
    md = (repo / "requirements.md").read_text(encoding="utf-8")
    assert "| python |" in md
    assert "| git |" in md
    assert "auto-generated" in md.lower()


def test_doctor_runs_all_checks_and_succeeds(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)

    def fake_check_all(requirements, **kw):
        return [
            RequirementResult(requirement=r, status=CheckStatus.OK, detected_version="x.y")
            for r in requirements
        ]

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)
    result = runner.invoke(app, ["doctor"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0
    assert "python" in result.stdout
    assert "git" in result.stdout


def test_doctor_exits_nonzero_when_any_check_fails(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)

    def fake_check_all(requirements, **kw):
        results = []
        for i, r in enumerate(requirements):
            status = CheckStatus.OK if i == 0 else CheckStatus.MISSING
            results.append(RequirementResult(requirement=r, status=status))
        return results

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)
    result = runner.invoke(app, ["doctor"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code != 0


def test_doctor_missing_requirements_yaml_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(app, ["doctor"], env={"LLM_REPO_ROOT": str(repo)})
    assert result.exit_code != 0
    assert "requirements.yaml" in (result.stdout or "") + (result.stderr or "")
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
pytest tests/integration/test_cli_doctor.py -v
```

Expected: failure — `doctor` command doesn't exist.

- [ ] **Step 3: Implement `commands/doctor.py`**

```python
# src/llm_cli/commands/doctor.py
"""`llm doctor` — verify external requirements; `llm doctor render-requirements` regenerates the markdown."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.doctor import (
    CheckStatus,
    check_all,
    load_requirements,
    render_requirements_md,
)

console = Console()
doctor_app = typer.Typer(
    name="doctor",
    help="Verify external requirements (CUDA driver, Python, hf CLI, ...).",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _repo_root() -> Path:
    explicit = os.environ.get("LLM_REPO_ROOT")
    return Path(explicit) if explicit else Path.cwd()


def _requirements_yaml(repo: Path) -> Path:
    path = repo / "requirements.yaml"
    if not path.is_file():
        console.print(f"[red]error:[/red] requirements.yaml not found at {path}")
        raise typer.Exit(code=1)
    return path


_STATUS_STYLES = {
    CheckStatus.OK: "green",
    CheckStatus.OUTDATED: "yellow",
    CheckStatus.MISSING: "red",
    CheckStatus.UNKNOWN: "magenta",
    CheckStatus.ERROR: "red",
}


@doctor_app.callback()
def doctor(ctx: typer.Context) -> None:
    """Run all requirement checks and print a status table."""
    if ctx.invoked_subcommand is not None:
        return

    repo = _repo_root()
    reqs = load_requirements(_requirements_yaml(repo))
    results = check_all(reqs)

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
    if bad:
        console.print(f"[red]{bad} requirement(s) need attention[/red]")
        raise typer.Exit(code=1)
    console.print("[green]all requirements satisfied[/green]")


@doctor_app.command("render-requirements", help="Regenerate requirements.md from requirements.yaml.")
def render_requirements() -> None:
    repo = _repo_root()
    reqs = load_requirements(_requirements_yaml(repo))
    md = render_requirements_md(reqs)
    out = repo / "requirements.md"
    out.write_text(md, encoding="utf-8")
    console.print(f"[green]wrote[/green] {out}")
```

- [ ] **Step 4: Wire into `main.py`**

Modify `src/llm_cli/main.py` to register the doctor sub-app. Final file:

```python
# src/llm_cli/main.py
"""LocalLLM CLI entrypoint."""
from typing import Optional

import typer

from llm_cli import __version__
from llm_cli.commands import init as init_cmd
from llm_cli.commands import specs as specs_cmd
from llm_cli.commands.doctor import doctor_app

app = typer.Typer(
    name="llm",
    help="LocalLLM — control plane for local LLM runtimes.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llm {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """LocalLLM CLI — manage runtimes, models, configs, and benchmarks."""


app.command("init", help="Read paths.yaml, create data-root dirs, write .llm-env.")(init_cmd.init)
app.command("specs", help="Regenerate the auto block in specs.md.")(specs_cmd.specs_command)
app.add_typer(doctor_app, name="doctor")
```

- [ ] **Step 5: Run all integration tests to verify they pass**

```powershell
pytest tests/integration/ -v
```

Expected: all integration tests PASS (help, init, specs, doctor).

- [ ] **Step 6: Generate the initial `requirements.md`**

```powershell
$env:LLM_REPO_ROOT = (Get-Location).Path
.\.venv\Scripts\Activate.ps1
llm doctor render-requirements
```

Verify `requirements.md` was created at the repo root and contains the requirements table.

- [ ] **Step 7: Commit**

```
git add src/llm_cli/commands/doctor.py src/llm_cli/main.py tests/integration/test_cli_doctor.py requirements.md
git commit -F-
```

Commit message:

```
feat(cli): add `llm doctor` and `llm doctor render-requirements`

doctor runs all checks from requirements.yaml and prints a colored status
table; exits 1 if any requirement is not OK. render-requirements
regenerates requirements.md (also committed in this commit).
```

---

## Task 15: `install.sh`

**Files:**
- Create: `install.sh`

Creates a venv at `~/llm/.cli-venv/`, runs `pip install -e <repo>`, and symlinks the resulting `llm` entrypoint into `~/.local/bin/`. Prints next-step instructions.

- [ ] **Step 1: Create `install.sh`**

```bash
#!/usr/bin/env bash
# Install the LocalLLM CLI into a venv and expose `llm` on PATH.
# Run inside WSL2 from the repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Read data_root from paths.yaml (very simple parser — assumes the canonical layout).
data_root_raw=$(awk -F': *' '/^data_root:/ {print $2; exit}' "$REPO_ROOT/paths.yaml")
data_root="${data_root_raw/#\~/$HOME}"
venv_dir="$data_root/.cli-venv"

echo "==> Creating venv at $venv_dir"
mkdir -p "$data_root"
"$PYTHON" -m venv "$venv_dir"

echo "==> Installing localllm-cli (editable) and dependencies"
"$venv_dir/bin/pip" install --upgrade pip
"$venv_dir/bin/pip" install -e "$REPO_ROOT"

local_bin="$HOME/.local/bin"
mkdir -p "$local_bin"
ln -sf "$venv_dir/bin/llm" "$local_bin/llm"

echo
echo "Installed. Make sure ~/.local/bin is on your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Next steps:"
echo "  llm init                    # create data-root subdirectories"
echo "  llm specs                   # generate specs.md"
echo "  llm doctor                  # verify requirements"
```

- [ ] **Step 2: Make it executable**

```powershell
git update-index --chmod=+x install.sh
```

(On WSL the equivalent is `chmod +x install.sh && git add install.sh`. The `git update-index --chmod=+x` form works from Windows.)

- [ ] **Step 3: Manual smoke test (deferred)**

Note in the commit body that the actual venv install can only be smoke-tested inside WSL, which is the next milestone's environment work. The script is reviewed by reading.

- [ ] **Step 4: Commit**

```
git add install.sh
git commit -F-
```

Commit message:

```
feat: add install.sh to bootstrap the CLI in WSL

Creates a venv at $LLM_DATA_ROOT/.cli-venv/, runs pip install -e .,
symlinks ~/.local/bin/llm. Prints next-step guidance. Manual smoke
test deferred to first WSL run.
```

---

## Task 16: Project README

**Files:**
- Create: `README.md`

A real, navigable README that explains the repo, links to the spec, and describes the bootstrap flow. Per the discipline rule, this is part of the same milestone that ships the foundation.

- [ ] **Step 1: Write `README.md`**

```markdown
# LocalLLM

Personal control plane for local LLM runtimes — manage runtime configurations,
benchmark them, and pin one as a "daily driver" that serves an OpenAI-compatible
endpoint.

This repo contains **text only** — manifests, configs, scripts, benchmark
results. Runtime source trees and model weights live in WSL2's native
filesystem under `~/llm/` (configurable via `paths.yaml`).

## Getting started (first time)

Inside WSL2:

```bash
# 1. Verify external prerequisites you'll need
cat requirements.md     # human-readable list
# (or after install:) llm doctor render-requirements && cat requirements.md

# 2. Install the CLI into a venv at ~/llm/.cli-venv/
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # if not already

# 3. Initialize data-root subdirectories
llm init

# 4. Document the machine
llm specs

# 5. Verify external requirements
llm doctor
```

## Layout

| Path | What it holds |
|---|---|
| `runtimes/{id}/` | Manifest + build/serve/healthcheck scripts for one runtime |
| `models/{id}/` | Manifest + pull script for one model (no weights — those live in `~/llm/models/`) |
| `configs/{id}.yaml` | One launch unit (runtime + model + flags) |
| `benchmarks/{id}/` | Wrapper around an existing benchmark tool, plus committed results |
| `state/` | Pinned daily driver, currently-running processes, history |
| `docs/` | HOWTOs and reference notes |
| `src/llm_cli/` | The Python CLI implementation |

See [`docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`](docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
for the full design.

## CLI commands (M1 — current)

| Command | Purpose |
|---|---|
| `llm init` | Read `paths.yaml`, create data-root subdirectories, write `.llm-env` |
| `llm specs` | Regenerate the auto block in `specs.md` |
| `llm specs --check` | Exit nonzero if `specs.md` differs from current detection |
| `llm specs --print` | Print detection without writing |
| `llm doctor` | Run all checks from `requirements.yaml` |
| `llm doctor render-requirements` | Regenerate `requirements.md` from `requirements.yaml` |

Future milestones add `llm list / status / build / pull / start / stop / switch / default / bench / results`.

## Discipline

When you change a workflow:
- Update the corresponding `docs/add-a-*.md` HOWTO **in the same commit**.
- If you add a new external dependency, update `requirements.yaml` and regenerate `requirements.md` in the same commit.
- A HOWTO that's more than two weeks stale relative to actual practice is a bug.
```

- [ ] **Step 2: Commit**

```
git add README.md
git commit -F-
```

Commit message:

```
docs: add project README with bootstrap flow and layout reference

Walks through install.sh -> llm init -> llm specs -> llm doctor for first-time
setup, and links to the design spec. Lists the M1 CLI commands.
```

---

## Task 17: WSL setup HOWTO

**Files:**
- Create: `docs/README.md`
- Create: `docs/wsl-setup.md`

Per the discipline rule, the foundation milestone ships the docs needed to actually use it — namely, how to set up WSL2 with systemd and the NVIDIA driver from scratch.

- [ ] **Step 1: Create `docs/README.md`**

```markdown
# LocalLLM Documentation

| Document | Purpose |
|---|---|
| [`wsl-setup.md`](wsl-setup.md) | One-time WSL2 + systemd + CUDA driver setup |

(Future milestones will add: `repo-conventions.md`, `add-a-runtime.md`, `add-a-model.md`, `add-a-config.md`, `add-a-benchmark.md`, `runtimes/{runtime-id}.md`.)
```

- [ ] **Step 2: Create `docs/wsl-setup.md`**

```markdown
# WSL2 Setup

One-time host/WSL setup for running the LocalLLM CLI and (later) actual runtimes.

## Prerequisites

- Windows 10 22H2+ or Windows 11
- An NVIDIA GPU
- Admin access on the host

## Steps

### 1. Install / update WSL2

In an elevated PowerShell:

```powershell
wsl --install -d Ubuntu-22.04   # if WSL not yet installed
wsl --update                    # ensure recent enough for systemd support
wsl --version                   # confirm WSL version >= 2.0
```

### 2. Install the NVIDIA driver on the host

Install the latest **Game Ready** or **Studio** driver for your GPU from
<https://www.nvidia.com/Download/index.aspx>. The host driver provides the
GPU passthrough into WSL2 — **do not** install a CUDA driver inside WSL.

Verify from WSL after rebooting:

```bash
nvidia-smi
```

You should see your GPU(s) listed with a driver version.

### 3. Enable systemd in WSL

Edit `/etc/wsl.conf` (create if missing):

```ini
[boot]
systemd=true
```

From PowerShell:

```powershell
wsl --shutdown
```

Re-open WSL, then verify:

```bash
systemctl is-system-running    # 'running' or 'degraded' is fine
```

### 4. Tune WSL memory and swap (optional but recommended)

Edit `~/.wslconfig` on the **Windows** host (e.g. `C:\Users\you\.wslconfig`):

```ini
[wsl2]
memory=48GB        # cap WSL's total RAM
swap=16GB
```

Adjust based on your physical RAM. `wsl --shutdown` to apply.

### 5. Install Python 3.11+, build tools, hf CLI

Inside WSL:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv build-essential cmake git curl jq
pip install -U huggingface_hub[cli]
```

### 6. Bootstrap the LocalLLM CLI

```bash
cd /mnt/c/Private/Projects/LocalLLM   # or wherever the repo lives
./install.sh
export PATH="$HOME/.local/bin:$PATH"
llm init
llm specs
llm doctor
```

`llm doctor` should report all requirements as OK. If something is missing or outdated, the doctor's output includes the install hint.

## Common pitfalls

- **`nvidia-smi: command not found` inside WSL** — you installed the driver inside WSL or used an old driver. Uninstall any in-WSL CUDA driver and install the latest host driver from NVIDIA.
- **Models stored on `/mnt/c/...`** — disastrously slow for weight loading. Always store under `~/llm/` (WSL ext4) or a dedicated mounted Linux drive.
- **`systemctl is-system-running` returns `offline`** — `/etc/wsl.conf` change didn't take. Confirm the file content, then `wsl --shutdown` and re-open.
- **`llm` not on PATH** — add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`.
```

- [ ] **Step 3: Commit**

```
git add docs/README.md docs/wsl-setup.md
git commit -F-
```

Commit message:

```
docs: add WSL setup HOWTO and docs index

wsl-setup.md walks through WSL2 install, NVIDIA driver, systemd, .wslconfig
tuning, prerequisite packages, and CLI bootstrap. Lists common pitfalls.
docs/README.md indexes the docs folder for current and future entries.
```

---

## Final verification

- [ ] **Step 1: Run the full test suite**

```powershell
pytest -v
```

Expected: every test PASSES (no failures, no errors).

- [ ] **Step 2: Manually exercise the CLI end-to-end**

```powershell
.\.venv\Scripts\Activate.ps1
$env:LLM_REPO_ROOT = (Get-Location).Path
llm --version
llm --help
llm init
llm specs --print           # should print a markdown block (most fields will be 'not detected' on Windows host)
llm doctor render-requirements
```

Expected: each command succeeds. `llm specs` and `llm doctor` will report many fields as not-detected when run from Windows (vs WSL); that's fine for verification of the code path.

- [ ] **Step 3: Confirm git state is clean**

```powershell
git status
git log --oneline
```

Expected: working tree clean. ~17 commits since the spec commit, one per task.

---

## Self-review checklist (run mentally before declaring milestone done)

1. **Spec coverage:** every M1 component named in the milestone goals (`init`, `specs`, `doctor`, `requirements.yaml`/`md`, `paths.yaml`, `install.sh`, WSL docs) has a task. ✓
2. **No placeholders:** no TBD/TODO in any task. ✓
3. **Type consistency:** `Paths`, `SystemSpecs`, `Requirement`, `RequirementResult`, `CheckStatus`, `CommandResult` are defined once and referenced by their final names throughout. The `MarkersMissingError`, `SPECS_START_MARKER`, `SPECS_END_MARKER`, `update_specs_markdown`, `render_specs_block`, `detect_all`, `load_requirements`, `check_all`, `render_requirements_md` symbols defined in earlier tasks are referenced exactly that way in later ones. ✓
4. **TDD discipline:** every implementation task starts with a failing test, runs it to confirm failure, implements, runs to confirm pass, then commits. Skeleton tasks (1, 11, 15, 16, 17) are explicitly noted as non-TDD because they create only data/docs.
5. **Commit cadence:** every task ends with a commit. No mega-commits.
