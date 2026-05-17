# Settings & Setup Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `paths.yaml` + `llm init` + `.llm-env` with a clean separation between machine-local settings (`~/.config/llm/config.yaml`) and repo content. Add `llm setup` (first-run + re-runnable) and `llm settings show / env / edit` commands. Make `repo_root` a settings key (no env-var override, no walk-up).

**Architecture:** A new module `src/llm_cli/core/settings.py` owns load/save/resolve/registry. Two new command modules (`commands/setup.py`, `commands/settings_cmd.py`) provide the CLI surface. `core/repo.py` shrinks to reading `Settings.repo_root`. `core/wsl.py` injects `LLM_*` env vars into bash subprocesses directly — `.llm-env` is gone. `paths.yaml`, `core/paths.py`, and `commands/init.py` are deleted.

**Tech Stack:** Python 3.11+, Typer (CLI), PyYAML (config), Rich (output), pytest (tests). Settings file location follows the XDG Base Directory spec (`$XDG_CONFIG_HOME` or `~/.config`).

**Reference spec:** `docs/superpowers/specs/2026-05-17-settings-and-setup-redesign.md`

**Running tests:** all commands assume you're in the repo root with the LocalLLM venv on PATH. From WSL:

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/c/Private/Projects/LocalLLM
/home/melih/llm/.cli-venv/bin/python -m pytest tests -q
```

Replace the venv path if yours differs (`./install.sh` puts it under `$LLM_DATA_ROOT/.cli-venv`).

---

## File Structure (locked at start of plan)

**Created:**

```
src/llm_cli/core/settings.py            # Tasks 1-6
src/llm_cli/commands/setup.py           # Tasks 8-10
src/llm_cli/commands/settings_cmd.py    # Tasks 11-14
tests/unit/test_settings.py             # Tasks 1-6
tests/integration/test_cli_setup.py     # Tasks 8-10
tests/integration/test_cli_settings.py  # Tasks 11-14
```

**Modified:**

```
src/llm_cli/main.py                     # Task 15
src/llm_cli/core/repo.py                # Task 17
src/llm_cli/core/wsl.py                 # Task 19
src/llm_cli/commands/artifacts.py       # Task 20
src/llm_cli/commands/specs.py           # Task 21
tests/conftest.py                       # Task 7
tests/unit/test_repo.py                 # Task 17
tests/unit/test_wsl.py                  # Task 19
tests/integration/test_cli_doctor.py    # Task 18
tests/integration/test_cli_specs.py     # Task 18
tests/integration/test_cli_milestone2.py # Task 18
install.sh                              # Task 25
README.md                               # Task 26
docs/repo-conventions.md                # Task 27
docs/add-a-runtime.md                   # Task 28
docs/add-a-model.md                     # Task 28
docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md # Task 29
.gitignore                              # Task 24
```

**Deleted:**

```
src/llm_cli/core/paths.py
src/llm_cli/commands/init.py
tests/unit/test_paths.py
tests/integration/test_cli_init.py
paths.yaml
```

---

## Phase 1 — Settings module foundation

### Task 1: Define `Settings` dataclass + defaults + `KEY_REGISTRY`

**Files:**
- Create: `src/llm_cli/core/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_settings.py
"""Tests for the user-level settings module."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.settings import KEY_REGISTRY, Settings, default_settings


def test_settings_dataclass_has_expected_fields() -> None:
    s = Settings(
        data_root=Path("/r"),
        repo_root=Path("/repo"),
        runtimes_dir=Path("/r/runtimes"),
        models_dir=Path("/r/models"),
        cache_dir=Path("/r/cache"),
    )
    assert s.data_root == Path("/r")
    assert s.repo_root == Path("/repo")
    assert s.runtimes_dir == Path("/r/runtimes")
    assert s.models_dir == Path("/r/models")
    assert s.cache_dir == Path("/r/cache")


def test_default_settings_has_data_root_only_and_no_repo_root() -> None:
    d = default_settings()
    assert d == {"data_root": "~/llm"}


def test_key_registry_has_required_keys() -> None:
    keys = set(KEY_REGISTRY.keys())
    assert keys == {"data_root", "repo_root", "runtimes_dir", "models_dir", "cache_dir"}
    assert KEY_REGISTRY["data_root"]["default"] == "~/llm"
    assert KEY_REGISTRY["repo_root"]["default"] is None
    assert KEY_REGISTRY["repo_root"]["required"] is True
    assert KEY_REGISTRY["data_root"]["required"] is True
    for k in ("runtimes_dir", "models_dir", "cache_dir"):
        assert KEY_REGISTRY[k]["required"] is False
        assert KEY_REGISTRY[k]["derived_from"] == "data_root"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm_cli.core.settings'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/llm_cli/core/settings.py
"""User-level settings stored at ~/.config/llm/config.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    data_root: Path
    repo_root: Path
    runtimes_dir: Path
    models_dir: Path
    cache_dir: Path


KEY_REGISTRY: dict[str, dict[str, Any]] = {
    "data_root": {
        "default": "~/llm",
        "required": True,
        "prompt": "Where should LocalLLM store runtimes, models, and cache?",
        "kind": "path",
    },
    "repo_root": {
        "default": None,
        "required": True,
        "prompt": "Path to the LocalLLM repo clone",
        "kind": "path",
    },
    "runtimes_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "runtimes",
        "prompt": "Override runtimes directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
    "models_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "models",
        "prompt": "Override models directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
    "cache_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "cache",
        "prompt": "Override cache directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
}


def default_settings() -> dict[str, str]:
    """The minimum stored dict; repo_root is filled in by `llm setup`."""
    return {"data_root": KEY_REGISTRY["data_root"]["default"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): introduce Settings dataclass and KEY_REGISTRY"
```

---

### Task 2: `settings_path()` — XDG-aware location

**Files:**
- Modify: `src/llm_cli/core/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_settings.py`:

```python
from llm_cli.core.settings import settings_path


def test_settings_path_defaults_to_home_config(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert settings_path() == tmp_path / ".config" / "llm" / "config.yaml"


def test_settings_path_honors_xdg_config_home(monkeypatch, tmp_path) -> None:
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert settings_path() == xdg / "llm" / "config.yaml"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_settings.py::test_settings_path_defaults_to_home_config -v`
Expected: FAIL with `ImportError: cannot import name 'settings_path'`.

- [ ] **Step 3: Write implementation**

Append to `src/llm_cli/core/settings.py`:

```python
import os


def settings_path() -> Path:
    """Resolve the settings file path honoring $XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "llm" / "config.yaml"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): add XDG-aware settings_path()"
```

---

### Task 3: `load_settings()` — parse YAML with validation

**Files:**
- Modify: `src/llm_cli/core/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
import pytest

from llm_cli.core.settings import (
    UnknownSettingError,
    load_settings,
)


def test_load_settings_missing_file_returns_empty_dict(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert load_settings() == {}


def test_load_settings_reads_yaml(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(
        "data_root: ~/x\nrepo_root: /tmp/repo\n", encoding="utf-8"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert load_settings() == {"data_root": "~/x", "repo_root": "/tmp/repo"}


def test_load_settings_rejects_unknown_keys(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text("oops: yes\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    with pytest.raises(UnknownSettingError) as exc:
        load_settings()
    assert "oops" in str(exc.value)


def test_load_settings_rejects_non_mapping(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    with pytest.raises(ValueError):
        load_settings()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL — `load_settings` and `UnknownSettingError` don't exist yet.

- [ ] **Step 3: Write implementation**

Append:

```python
import yaml


class UnknownSettingError(ValueError):
    """Raised when the settings file contains a key that is not in KEY_REGISTRY."""


def load_settings() -> dict[str, str]:
    """Load raw settings from disk. Missing file → empty dict."""
    path = settings_path()
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    unknown = sorted(k for k in raw if k not in KEY_REGISTRY)
    if unknown:
        raise UnknownSettingError(
            f"{path}: unknown setting(s): {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
    return {str(k): str(v) for k, v in raw.items()}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): add load_settings() with key validation"
```

---

### Task 4: `save_settings()` — write YAML round-trip

**Files:**
- Modify: `src/llm_cli/core/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from llm_cli.core.settings import save_settings


def test_save_settings_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    save_settings({"data_root": "~/llm", "repo_root": "/some/repo"})
    assert load_settings() == {"data_root": "~/llm", "repo_root": "/some/repo"}


def test_save_settings_creates_parent_dirs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "deep" / "xdg"))
    save_settings({"data_root": "~/llm", "repo_root": "/r"})
    assert (tmp_path / "deep" / "xdg" / "llm" / "config.yaml").is_file()


def test_save_settings_rejects_unknown_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    with pytest.raises(UnknownSettingError):
        save_settings({"oops": "yes"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL — `save_settings` not defined.

- [ ] **Step 3: Write implementation**

Append:

```python
def save_settings(values: dict[str, str]) -> Path:
    """Write the settings dict to disk; returns the path written."""
    unknown = sorted(k for k in values if k not in KEY_REGISTRY)
    if unknown:
        raise UnknownSettingError(
            f"unknown setting(s): {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: values[k] for k in KEY_REGISTRY if k in values}
    path.write_text(
        yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (12 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): add save_settings() with key validation"
```

---

### Task 5: `resolve()` — fill in derived dirs + expand `~`

**Files:**
- Modify: `src/llm_cli/core/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
from llm_cli.core.settings import MissingSettingError, resolve


def test_resolve_derives_dir_keys_from_data_root() -> None:
    out = resolve({"data_root": "/dr", "repo_root": "/repo"})
    assert out.data_root == Path("/dr")
    assert out.repo_root == Path("/repo")
    assert out.runtimes_dir == Path("/dr/runtimes")
    assert out.models_dir == Path("/dr/models")
    assert out.cache_dir == Path("/dr/cache")


def test_resolve_honors_explicit_dir_overrides() -> None:
    out = resolve(
        {
            "data_root": "/dr",
            "repo_root": "/repo",
            "runtimes_dir": "/mnt/d/rt",
        }
    )
    assert out.runtimes_dir == Path("/mnt/d/rt")
    assert out.models_dir == Path("/dr/models")


def test_resolve_expands_tilde(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    out = resolve({"data_root": "~/llm", "repo_root": "~/r"})
    assert out.data_root == tmp_path / "llm"
    assert out.repo_root == tmp_path / "r"
    assert out.runtimes_dir == tmp_path / "llm" / "runtimes"


def test_resolve_uses_default_for_data_root_when_missing() -> None:
    out = resolve({"repo_root": "/r"})
    assert out.data_root == Path("~/llm").expanduser()


def test_resolve_raises_when_repo_root_missing() -> None:
    with pytest.raises(MissingSettingError) as exc:
        resolve({"data_root": "/dr"})
    assert "repo_root" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL — `resolve` and `MissingSettingError` not defined.

- [ ] **Step 3: Write implementation**

Append:

```python
class MissingSettingError(ValueError):
    """Raised when a required setting (e.g. repo_root) is absent."""


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def resolve(values: dict[str, str]) -> Settings:
    """Return a fully-populated Settings, filling defaults + derived dir keys."""
    data_root_raw = values.get("data_root", KEY_REGISTRY["data_root"]["default"])
    data_root = _expand(data_root_raw)

    repo_root_raw = values.get("repo_root")
    if not repo_root_raw:
        raise MissingSettingError(
            "repo_root is not configured; run `llm setup` from inside the repo"
        )
    repo_root = _expand(repo_root_raw)

    def _dir(key: str, suffix: str) -> Path:
        override = values.get(key)
        return _expand(override) if override else data_root / suffix

    return Settings(
        data_root=data_root,
        repo_root=repo_root,
        runtimes_dir=_dir("runtimes_dir", "runtimes"),
        models_dir=_dir("models_dir", "models"),
        cache_dir=_dir("cache_dir", "cache"),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (17 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): add resolve() to fill defaults and derived dirs"
```

---

### Task 6: `ensure_data_dirs()` helper

**Files:**
- Modify: `src/llm_cli/core/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from llm_cli.core.settings import ensure_data_dirs


def test_ensure_data_dirs_creates_all_resolved_dirs(tmp_path) -> None:
    s = resolve({"data_root": str(tmp_path / "dr"), "repo_root": str(tmp_path)})
    ensure_data_dirs(s)
    assert (tmp_path / "dr").is_dir()
    assert (tmp_path / "dr" / "runtimes").is_dir()
    assert (tmp_path / "dr" / "models").is_dir()
    assert (tmp_path / "dr" / "cache").is_dir()


def test_ensure_data_dirs_is_idempotent(tmp_path) -> None:
    s = resolve({"data_root": str(tmp_path / "dr"), "repo_root": str(tmp_path)})
    ensure_data_dirs(s)
    ensure_data_dirs(s)
    assert (tmp_path / "dr").is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL — `ensure_data_dirs` not defined.

- [ ] **Step 3: Write implementation**

Append:

```python
def ensure_data_dirs(settings: Settings) -> None:
    """Create data_root + the three resolved data subdirectories if absent."""
    for target in (
        settings.data_root,
        settings.runtimes_dir,
        settings.models_dir,
        settings.cache_dir,
    ):
        target.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (19 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): add ensure_data_dirs() helper"
```

---

### Task 7: Add `xdg_isolated` autouse fixture for test isolation

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update `conftest.py`**

Replace `tests/conftest.py` with:

```python
"""Shared test setup: src/ on path; isolate XDG_CONFIG_HOME for every test."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def xdg_isolated(tmp_path_factory, monkeypatch):
    """Redirect $XDG_CONFIG_HOME so tests never touch real user settings."""
    cfg = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    return cfg
```

- [ ] **Step 2: Run the full suite to confirm nothing regressed**

Run: `pytest tests -q`
Expected: same number of tests passing as before this task; no new failures.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: autouse XDG_CONFIG_HOME isolation fixture"
```

---

## Phase 2 — `llm setup` command

### Task 8: `llm setup --default` (non-interactive)

**Files:**
- Create: `src/llm_cli/commands/setup.py`
- Test: `tests/integration/test_cli_setup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_setup.py
"""Integration tests for `llm setup`."""
from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_setup_default_writes_settings_and_creates_dirs(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "data"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LLM_DEFAULT_DATA_ROOT", str(data))

    result = runner.invoke(app, ["setup", "--default"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    assert cfg.is_file()
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["repo_root"] == str(repo)
    assert stored["data_root"] == str(data)
    assert data.is_dir()
    assert (data / "runtimes").is_dir()
```

Notes:
- The `xdg_isolated` autouse fixture already points `$XDG_CONFIG_HOME` at a fresh tmp dir, so `~/.config/llm/config.yaml` resolves to a clean location.
- `LLM_DEFAULT_DATA_ROOT` is an opt-in test hook used by `setup --default` so we don't actually create `~/llm` during tests; covered in step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_setup.py -v`
Expected: FAIL — `setup` command doesn't exist.

- [ ] **Step 3: Write implementation**

```python
# src/llm_cli/commands/setup.py
"""`llm setup` — first-run interactive configurator."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from llm_cli.core.settings import (
    KEY_REGISTRY,
    ensure_data_dirs,
    load_settings,
    resolve,
    save_settings,
    settings_path,
)

console = Console()


def _default_data_root() -> str:
    return os.environ.get(
        "LLM_DEFAULT_DATA_ROOT", KEY_REGISTRY["data_root"]["default"]
    )


def setup(
    default: bool = typer.Option(
        False, "--default", help="Non-interactive: use defaults for every key."
    ),
) -> None:
    """Configure machine-local settings (~/.config/llm/config.yaml)."""
    repo_root = Path.cwd().resolve()
    data_root = _default_data_root()
    stored = {"data_root": data_root, "repo_root": str(repo_root)}

    if not default:
        # Interactive path is filled in by Tasks 9 and 10. For now, --default
        # is the only supported mode.
        console.print(
            "[yellow]interactive setup not yet implemented; "
            "re-run with --default[/yellow]"
        )
        raise typer.Exit(code=2)

    path = save_settings(stored)
    resolved = resolve(load_settings())
    ensure_data_dirs(resolved)
    console.print(f"[green]wrote[/green] {path}")
    console.print(f"[green]data_root[/green]: {resolved.data_root}")
    console.print(f"[green]repo_root[/green]: {resolved.repo_root}")
```

Register the command in `src/llm_cli/main.py` (just enough to make the test reach it):

```python
# add near the other imports
from llm_cli.commands import setup as setup_cmd

# add near the other app.command(...) calls
app.command("setup", help="Configure machine-local settings.")(setup_cmd.setup)
```

- [ ] **Step 4: Run test**

Run: `pytest tests/integration/test_cli_setup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/setup.py src/llm_cli/main.py tests/integration/test_cli_setup.py
git commit -m "feat(setup): add `llm setup --default` (non-interactive)"
```

---

### Task 9: `llm setup` interactive — data_root prompt + default layout

**Files:**
- Modify: `src/llm_cli/commands/setup.py`
- Test: `tests/integration/test_cli_setup.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_setup_interactive_default_layout(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "mydata"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # data_root prompt → custom path; layout prompt → empty (accept default Y)
    user_input = f"{data}\n\n"
    result = runner.invoke(app, ["setup"], input=user_input, catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored == {"data_root": str(data), "repo_root": str(repo)}
    assert (data / "runtimes").is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_setup.py::test_setup_interactive_default_layout -v`
Expected: FAIL — interactive path exits with code 2.

- [ ] **Step 3: Replace the interactive stub**

In `src/llm_cli/commands/setup.py`, replace the whole `setup()` function with:

```python
def setup(
    default: bool = typer.Option(
        False, "--default", help="Non-interactive: use defaults for every key."
    ),
) -> None:
    """Configure machine-local settings (~/.config/llm/config.yaml)."""
    repo_root = Path.cwd().resolve()
    stored: dict[str, str] = {"repo_root": str(repo_root)}

    if default:
        stored["data_root"] = _default_data_root()
    else:
        stored["data_root"] = typer.prompt(
            KEY_REGISTRY["data_root"]["prompt"],
            default=_default_data_root(),
        )
        granular = typer.confirm(
            "Use default subdirectory layout under data_root?",
            default=True,
        )
        if not granular:
            stored.update(_prompt_dir_overrides(stored["data_root"]))

    path = save_settings(stored)
    resolved = resolve(load_settings())
    ensure_data_dirs(resolved)
    console.print(f"[green]wrote[/green] {path}")
    console.print(f"[green]data_root[/green]: {resolved.data_root}")
    console.print(f"[green]runtimes_dir[/green]: {resolved.runtimes_dir}")
    console.print(f"[green]models_dir[/green]: {resolved.models_dir}")
    console.print(f"[green]cache_dir[/green]: {resolved.cache_dir}")
    console.print(f"[green]repo_root[/green]: {resolved.repo_root}")


def _prompt_dir_overrides(data_root: str) -> dict[str, str]:
    """Placeholder; granular prompts are added in Task 10."""
    return {}
```

- [ ] **Step 4: Run test**

Run: `pytest tests/integration/test_cli_setup.py -v`
Expected: PASS (both setup tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/setup.py tests/integration/test_cli_setup.py
git commit -m "feat(setup): interactive data_root prompt + default layout"
```

---

### Task 10: `llm setup` interactive — granular layout branch

**Files:**
- Modify: `src/llm_cli/commands/setup.py`
- Test: `tests/integration/test_cli_setup.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_setup_interactive_granular_layout(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "dr"
    rt_override = tmp_path / "rtcustom"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    user_input = (
        f"{data}\n"        # data_root
        "n\n"             # granular layout? n
        f"{rt_override}\n"  # runtimes_dir override
        "\n"              # models_dir (empty → derive)
        "\n"              # cache_dir (empty → derive)
    )
    result = runner.invoke(app, ["setup"], input=user_input, catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["repo_root"] == str(repo)
    assert stored["data_root"] == str(data)
    assert stored["runtimes_dir"] == str(rt_override)
    assert "models_dir" not in stored
    assert "cache_dir" not in stored
    assert rt_override.is_dir()
    assert (data / "models").is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_setup.py::test_setup_interactive_granular_layout -v`
Expected: FAIL — granular prompts not asked, `runtimes_dir` missing.

- [ ] **Step 3: Implement `_prompt_dir_overrides`**

Replace the placeholder with:

```python
def _prompt_dir_overrides(data_root: str) -> dict[str, str]:
    """Prompt for each dir key; empty answer → key is omitted (stays derived)."""
    overrides: dict[str, str] = {}
    data_root_path = Path(data_root).expanduser()
    for key in ("runtimes_dir", "models_dir", "cache_dir"):
        meta = KEY_REGISTRY[key]
        derived = data_root_path / meta["derived_suffix"]
        answer = typer.prompt(meta["prompt"], default="", show_default=False)
        answer = answer.strip()
        if answer and answer != str(derived):
            overrides[key] = answer
    return overrides
```

- [ ] **Step 4: Run all setup tests**

Run: `pytest tests/integration/test_cli_setup.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/setup.py tests/integration/test_cli_setup.py
git commit -m "feat(setup): granular per-directory override prompts"
```

---

## Phase 3 — `llm settings` sub-app

### Task 11: `llm settings show`

**Files:**
- Create: `src/llm_cli/commands/settings_cmd.py`
- Create: `tests/integration/test_cli_settings.py`
- Modify: `src/llm_cli/main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_settings.py
"""Integration tests for `llm settings ...`."""
from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _write_settings(monkeypatch, tmp_path, **kv) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(yaml.safe_dump(kv), encoding="utf-8")
    return cfg


def test_settings_show_prints_path_and_resolved(tmp_path, monkeypatch) -> None:
    cfg = _write_settings(
        monkeypatch, tmp_path, data_root=str(tmp_path / "d"), repo_root=str(tmp_path / "r")
    )
    result = runner.invoke(app, ["settings", "show"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    assert str(cfg) in result.stdout
    assert str(tmp_path / "d") in result.stdout
    assert str(tmp_path / "r" ) in result.stdout
    assert "runtimes_dir" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: FAIL — `settings` sub-command doesn't exist.

- [ ] **Step 3: Write implementation**

```python
# src/llm_cli/commands/settings_cmd.py
"""`llm settings ...` — inspect and edit user-level settings."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.core.settings import (
    KEY_REGISTRY,
    load_settings,
    resolve,
    settings_path,
)

console = Console()

settings_app = typer.Typer(help="Inspect and edit user-level settings.")


@settings_app.command("show")
def show() -> None:
    """Print the settings file path, stored contents, and resolved view."""
    path = settings_path()
    stored = load_settings()
    console.print(f"[bold]file[/bold]: {path}")
    console.print("[bold]stored[/bold]:")
    if stored:
        for k in KEY_REGISTRY:
            if k in stored:
                console.print(f"  {k}: {stored[k]}")
    else:
        console.print("  (empty)")
    console.print("[bold]resolved[/bold]:")
    resolved = resolve(stored)
    for k in KEY_REGISTRY:
        console.print(f"  {k}: {getattr(resolved, k)}")
```

Wire into `src/llm_cli/main.py`:

```python
# add near the other imports
from llm_cli.commands.settings_cmd import settings_app

# add near the other app.add_typer(...) calls
app.add_typer(settings_app, name="settings")
```

- [ ] **Step 4: Run test**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/settings_cmd.py src/llm_cli/main.py tests/integration/test_cli_settings.py
git commit -m "feat(settings): add `llm settings show`"
```

---

### Task 12: `llm settings env`

**Files:**
- Modify: `src/llm_cli/commands/settings_cmd.py`
- Test: `tests/integration/test_cli_settings.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_settings_env_prints_export_lines(tmp_path, monkeypatch) -> None:
    _write_settings(
        monkeypatch, tmp_path, data_root=str(tmp_path / "d"), repo_root=str(tmp_path / "r")
    )
    result = runner.invoke(app, ["settings", "env"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    lines = result.stdout.strip().splitlines()
    assert f"export LLM_DATA_ROOT={tmp_path / 'd'}" in lines
    assert f"export LLM_REPO_ROOT={tmp_path / 'r'}" in lines
    assert f"export LLM_RUNTIMES={tmp_path / 'd' / 'runtimes'}" in lines
    assert f"export LLM_MODELS={tmp_path / 'd' / 'models'}" in lines
    assert f"export LLM_CACHE={tmp_path / 'd' / 'cache'}" in lines


def test_settings_env_shell_escapes_values(tmp_path, monkeypatch) -> None:
    weird = tmp_path / "with space"
    _write_settings(
        monkeypatch, tmp_path, data_root=str(weird), repo_root=str(tmp_path / "r")
    )
    result = runner.invoke(app, ["settings", "env"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "'" in result.stdout  # shlex.quote wraps values containing spaces
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: FAIL — `env` sub-command doesn't exist.

- [ ] **Step 3: Write implementation**

Append to `src/llm_cli/commands/settings_cmd.py`:

```python
import shlex


_ENV_MAPPING = (
    ("LLM_DATA_ROOT", "data_root"),
    ("LLM_REPO_ROOT", "repo_root"),
    ("LLM_RUNTIMES", "runtimes_dir"),
    ("LLM_MODELS", "models_dir"),
    ("LLM_CACHE", "cache_dir"),
)


@settings_app.command("env")
def env() -> None:
    """Print `export LLM_*=...` lines for `eval \"$(llm settings env)\"`."""
    resolved = resolve(load_settings())
    for var, attr in _ENV_MAPPING:
        value = getattr(resolved, attr).as_posix()
        typer.echo(f"export {var}={shlex.quote(value)}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/settings_cmd.py tests/integration/test_cli_settings.py
git commit -m "feat(settings): add `llm settings env` (eval-friendly export lines)"
```

---

### Task 13: `llm settings edit <key>` (interactive)

**Files:**
- Modify: `src/llm_cli/commands/settings_cmd.py`
- Test: `tests/integration/test_cli_settings.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_settings_edit_updates_existing_key(tmp_path, monkeypatch) -> None:
    _write_settings(
        monkeypatch, tmp_path, data_root="~/llm", repo_root=str(tmp_path / "r")
    )
    new_dr = tmp_path / "new"
    result = runner.invoke(
        app, ["settings", "edit", "data_root"], input=f"{new_dr}\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["data_root"] == str(new_dr)


def test_settings_edit_unknown_key_errors(tmp_path, monkeypatch) -> None:
    _write_settings(
        monkeypatch, tmp_path, data_root="~/llm", repo_root=str(tmp_path / "r")
    )
    result = runner.invoke(app, ["settings", "edit", "nope"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "nope" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: FAIL — `edit` sub-command doesn't exist.

- [ ] **Step 3: Write implementation**

Append to `src/llm_cli/commands/settings_cmd.py`:

```python
from llm_cli.core.settings import (  # noqa: E402 — group with other settings imports
    ensure_data_dirs,
    save_settings,
)


@settings_app.command("edit")
def edit(
    key: str = typer.Argument(..., help="Setting key to edit."),
    default: bool = typer.Option(
        False, "--default", help="Reset key to its built-in default."
    ),
) -> None:
    """Edit a single settings key, interactively by default."""
    if key not in KEY_REGISTRY:
        console.print(
            f"[red]error:[/red] unknown setting {key!r}. "
            f"Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
        raise typer.Exit(code=1)

    stored = load_settings()
    meta = KEY_REGISTRY[key]

    if default:
        if meta.get("required") and meta.get("default") is None:
            console.print(
                f"[red]error:[/red] {key!r} has no built-in default; "
                f"use `llm settings edit {key}` to set a new value."
            )
            raise typer.Exit(code=1)
        if meta["default"] is None:
            stored.pop(key, None)
        else:
            stored[key] = meta["default"]
    else:
        current = stored.get(key) or meta.get("default") or ""
        answer = typer.prompt(meta["prompt"], default=current).strip()
        if answer:
            stored[key] = answer
        else:
            stored.pop(key, None)

    save_settings(stored)
    resolved = resolve(stored)
    ensure_data_dirs(resolved)
    console.print(f"[green]updated[/green] {key}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/settings_cmd.py tests/integration/test_cli_settings.py
git commit -m "feat(settings): add interactive `llm settings edit <key>`"
```

---

### Task 14: `llm settings edit <key> --default` semantics

**Files:**
- Test only: `tests/integration/test_cli_settings.py`

This task asserts the `--default` branches behave per spec; the implementation was added in Task 13.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_settings_edit_default_data_root_resets(tmp_path, monkeypatch) -> None:
    _write_settings(
        monkeypatch, tmp_path, data_root=str(tmp_path / "old"), repo_root=str(tmp_path / "r")
    )
    result = runner.invoke(
        app, ["settings", "edit", "data_root", "--default"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.stdout
    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["data_root"] == "~/llm"


def test_settings_edit_default_runtimes_dir_removes_override(tmp_path, monkeypatch) -> None:
    _write_settings(
        monkeypatch,
        tmp_path,
        data_root=str(tmp_path / "dr"),
        repo_root=str(tmp_path / "r"),
        runtimes_dir=str(tmp_path / "override"),
    )
    result = runner.invoke(
        app, ["settings", "edit", "runtimes_dir", "--default"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.stdout
    cfg = Path.home() / ".config" / "llm" / "config.yaml"
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert "runtimes_dir" not in stored


def test_settings_edit_default_repo_root_errors(tmp_path, monkeypatch) -> None:
    _write_settings(
        monkeypatch, tmp_path, data_root="~/llm", repo_root=str(tmp_path / "r")
    )
    result = runner.invoke(
        app, ["settings", "edit", "repo_root", "--default"], catch_exceptions=False
    )
    assert result.exit_code != 0
    assert "repo_root" in result.stdout
```

- [ ] **Step 2: Run all settings tests**

Run: `pytest tests/integration/test_cli_settings.py -v`
Expected: PASS (all settings tests including the new three).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_cli_settings.py
git commit -m "test(settings): cover --default semantics for edit"
```

---

## Phase 4 — Wire commands + remove `llm init`

### Task 15: Remove `llm init` from `main.py`, delete `init.py` and its tests

**Files:**
- Modify: `src/llm_cli/main.py`
- Delete: `src/llm_cli/commands/init.py`, `tests/integration/test_cli_init.py`

- [ ] **Step 1: Modify `main.py`**

Remove these two lines from `src/llm_cli/main.py`:

```python
from llm_cli.commands import init as init_cmd
```

and

```python
app.command("init", help="Read paths.yaml, create data-root dirs, write .llm-env.")(init_cmd.init)
```

- [ ] **Step 2: Delete files**

```bash
git rm src/llm_cli/commands/init.py tests/integration/test_cli_init.py
```

- [ ] **Step 3: Confirm `llm init` is gone**

Run: `llm --help` should not list `init`. Also run the test suite to confirm no import errors:

Run: `pytest tests -q`
Expected: tests pass; one fewer integration test file.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(cli): remove `llm init` (absorbed into `llm setup`)"
```

---

### Task 16: Add `.llm-env` to `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append to `.gitignore`**

Add a line `\.llm-env` to `.gitignore` (creating the file if necessary). Verify with `git check-ignore -v .llm-env` (after creating a dummy file).

- [ ] **Step 2: Remove any tracked `.llm-env`**

```bash
git rm --cached .llm-env 2>/dev/null || true
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore .llm-env (legacy generated file)"
```

---

## Phase 5 — Migrate consumers

### Task 17: Migrate `core/repo.py` to read `settings.repo_root`

**Files:**
- Modify: `src/llm_cli/core/repo.py`
- Modify: `tests/unit/test_repo.py`

- [ ] **Step 1: Replace the test file**

Overwrite `tests/unit/test_repo.py` with:

```python
"""Tests for repo root discovery via settings."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.repo import RepoRootMissing, repo_root
from llm_cli.core.settings import save_settings


def test_repo_root_reads_from_settings(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    save_settings({"data_root": str(tmp_path / "d"), "repo_root": str(repo)})
    assert repo_root() == repo.resolve()


def test_repo_root_raises_when_missing(tmp_path) -> None:
    with pytest.raises(RepoRootMissing):
        repo_root()


def test_repo_root_raises_when_pointed_at_nonexistent_dir(tmp_path) -> None:
    save_settings({"data_root": str(tmp_path / "d"), "repo_root": str(tmp_path / "ghost")})
    with pytest.raises(RepoRootMissing):
        repo_root()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_repo.py -v`
Expected: FAIL — `RepoRootMissing` doesn't exist; old logic still uses walk-up.

- [ ] **Step 3: Replace `core/repo.py`**

```python
"""Resolve the LocalLLM repo root from user settings."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.settings import (
    MissingSettingError,
    load_settings,
    resolve,
)


class RepoRootMissing(RuntimeError):
    """Raised when the configured repo_root is missing or invalid."""


def repo_root() -> Path:
    """Return the absolute path of the LocalLLM repo as configured."""
    try:
        resolved = resolve(load_settings())
    except MissingSettingError as exc:
        raise RepoRootMissing(str(exc)) from exc
    if not resolved.repo_root.is_dir():
        raise RepoRootMissing(
            f"repo_root points at {resolved.repo_root}, which is not a directory; "
            "run `llm settings edit repo_root` to fix"
        )
    return resolved.repo_root.resolve()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_repo.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/repo.py tests/unit/test_repo.py
git commit -m "refactor(repo): read repo_root from settings (no walk-up)"
```

---

### Task 18: Migrate existing integration tests off `LLM_REPO_ROOT`

**Files:**
- Modify: `tests/integration/test_cli_doctor.py`
- Modify: `tests/integration/test_cli_specs.py`
- Modify: `tests/integration/test_cli_milestone2.py`

The pattern: every `env={"LLM_REPO_ROOT": str(repo)}` is replaced with a call to a new helper that writes a settings file under the autouse `xdg_isolated` fixture.

- [ ] **Step 1: Add helper to each test file**

At the top of each of the three files (after imports), add:

```python
def _configure(monkeypatch, tmp_path, repo) -> None:
    """Point HOME (and therefore XDG default) at tmp_path, write settings."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg_dir = Path.home() / ".config" / "llm"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.yaml").write_text(
        f"data_root: {tmp_path}/data\nrepo_root: {repo}\n",
        encoding="utf-8",
    )
```

- [ ] **Step 2: Replace `env=` calls**

In each test that previously did:

```python
result = runner.invoke(app, [...], env={"LLM_REPO_ROOT": str(repo)})
```

change it to:

```python
_configure(monkeypatch, tmp_path, repo)
result = runner.invoke(app, [...])
```

(and add `monkeypatch` to the test signature if missing).

Concrete replacements:

- `tests/integration/test_cli_doctor.py` — all three tests in the file (`test_doctor_render_requirements_writes_md`, `test_doctor_reports_check_results`, plus any others that use `LLM_REPO_ROOT`). The repo fixture in those tests is the local `repo = tmp_path / "repo"` already in each test.
- `tests/integration/test_cli_specs.py` — `test_specs_writes_specs_md_when_missing`, `test_specs_check_detects_drift`, `test_specs_print_does_not_write`. Same pattern.
- `tests/integration/test_cli_milestone2.py` — every test in the file (`test_list_runtimes_table`, `test_list_json`, `test_list_invalid_kind_errors`, `test_config_validate_ok`, `test_config_show_resolves_env`, `test_build_calls_run_repo_bash`, `test_pull_calls_run_repo_bash`, `test_build_unknown_runtime_errors`). Each one already has `repo = _make_repo(tmp_path)`; add `_configure(monkeypatch, tmp_path, repo)` after that line.

- [ ] **Step 3: Run the suite**

Run: `pytest tests -q`
Expected: PASS (no regression from the migration).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_cli_doctor.py tests/integration/test_cli_specs.py tests/integration/test_cli_milestone2.py
git commit -m "test: migrate integration tests off LLM_REPO_ROOT to settings file"
```

---

### Task 19: Migrate `core/wsl.py` — inject env from Settings; drop `.llm-env` source

**Files:**
- Modify: `src/llm_cli/core/wsl.py`
- Modify: `tests/unit/test_wsl.py`

- [ ] **Step 1: Update the test file**

Append to `tests/unit/test_wsl.py`:

```python
from unittest.mock import patch

from llm_cli.core.settings import Settings
from llm_cli.core import wsl


def _fake_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "d",
        repo_root=tmp_path / "r",
        runtimes_dir=tmp_path / "d" / "runtimes",
        models_dir=tmp_path / "d" / "models",
        cache_dir=tmp_path / "d" / "cache",
    )


def test_run_repo_bash_injects_env_from_settings(tmp_path) -> None:
    s = _fake_settings(tmp_path)
    captured: dict[str, str] = {}

    def fake_call(cmd, env=None):
        captured.update(env or {})
        return 0

    with patch.object(wsl.subprocess, "call", side_effect=fake_call):
        rc = wsl.run_repo_bash(s, "runtimes/x/build.sh")
    assert rc == 0
    assert captured["LLM_DATA_ROOT"] == (tmp_path / "d").as_posix()
    assert captured["LLM_REPO_ROOT"] == (tmp_path / "r").as_posix()
    assert captured["LLM_RUNTIMES"] == (tmp_path / "d" / "runtimes").as_posix()
    assert captured["LLM_MODELS"] == (tmp_path / "d" / "models").as_posix()
    assert captured["LLM_CACHE"] == (tmp_path / "d" / "cache").as_posix()


def test_run_repo_bash_no_longer_sources_llm_env(tmp_path) -> None:
    s = _fake_settings(tmp_path)
    captured_cmd: list[str] = []

    def fake_call(cmd, env=None):
        captured_cmd.extend(cmd)
        return 0

    with patch.object(wsl.subprocess, "call", side_effect=fake_call):
        wsl.run_repo_bash(s, "runtimes/x/build.sh")
    joined = " ".join(captured_cmd)
    assert ".llm-env" not in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_wsl.py -v`
Expected: FAIL — `run_repo_bash` signature still takes `Path`, not `Settings`.

- [ ] **Step 3: Update `wsl.py`**

Replace `run_repo_bash` in `src/llm_cli/core/wsl.py` with:

```python
from llm_cli.core.settings import Settings  # add near other imports


def run_repo_bash(
    settings: Settings,
    script_posix_relpath: str,
    script_args: list[str] | None = None,
    *,
    extra_env: dict[str, str] | None = None,
) -> int:
    """Run a bash script relative to settings.repo_root with LLM_* env injected."""
    script_args = script_args or []
    repo_wsl = to_wsl_path(settings.repo_root)
    script_wsl = f"{repo_wsl}/{script_posix_relpath.lstrip('/')}"
    args_str = " ".join(shlex.quote(a) for a in script_args)
    cmd_tail = f"bash {shlex.quote(script_wsl)}" + (f" {args_str}" if args_str else "")
    inner = (
        "set -euo pipefail; "
        f"cd {shlex.quote(repo_wsl)}; "
        f"{cmd_tail}"
    )
    bash = ["bash", "-lc", inner]
    full_cmd = ["wsl", "-e", *bash] if is_windows() else bash
    merged = os.environ.copy()
    merged.update(
        {
            "LLM_DATA_ROOT": settings.data_root.as_posix(),
            "LLM_REPO_ROOT": settings.repo_root.as_posix(),
            "LLM_RUNTIMES": settings.runtimes_dir.as_posix(),
            "LLM_MODELS": settings.models_dir.as_posix(),
            "LLM_CACHE": settings.cache_dir.as_posix(),
        }
    )
    if extra_env:
        merged.update(extra_env)
    return int(subprocess.call(full_cmd, env=merged))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_wsl.py -v`
Expected: PASS (existing tests still green + the two new ones).

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/wsl.py tests/unit/test_wsl.py
git commit -m "refactor(wsl): inject LLM_* env from Settings, drop .llm-env source"
```

---

### Task 20: Update `commands/artifacts.py` to pass `Settings` to `run_repo_bash`

**Files:**
- Modify: `src/llm_cli/commands/artifacts.py`
- Modify: `tests/integration/test_cli_milestone2.py` (the build/pull mock signature)

- [ ] **Step 1: Update the artifacts module**

Replace the body of `src/llm_cli/commands/artifacts.py`:

```python
"""`llm build` and `llm pull` — run WSL bash scripts for runtimes and models."""
from __future__ import annotations

import typer
from rich.console import Console

from llm_cli.core import registry
from llm_cli.core.repo import repo_root
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.wsl import run_repo_bash

console = Console()


def build_runtime(runtime_id: str = typer.Argument(..., help="Runtime id.")) -> None:
    """Run `runtimes/<id>/build.sh` inside WSL with LLM_* env injected."""
    repo = repo_root()
    rec = registry.get_runtime(repo, runtime_id)
    if rec is None:
        console.print(f"[red]error:[/red] unknown runtime {runtime_id!r}")
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    code = run_repo_bash(settings, f"runtimes/{runtime_id}/build.sh")
    if code != 0:
        console.print(f"[red]build failed[/red] with exit code {code}")
        raise typer.Exit(code=code)


def pull_model(model_id: str = typer.Argument(..., help="Model id.")) -> None:
    """Run `models/<id>/pull.sh` inside WSL with LLM_* env injected."""
    repo = repo_root()
    rec = registry.get_model(repo, model_id)
    if rec is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    settings = resolve(load_settings())
    code = run_repo_bash(settings, f"models/{model_id}/pull.sh")
    if code != 0:
        console.print(f"[red]pull failed[/red] with exit code {code}")
        raise typer.Exit(code=code)
```

- [ ] **Step 2: Update the build/pull mocks in the integration test**

In `tests/integration/test_cli_milestone2.py`, the patched calls look like:

```python
@patch("llm_cli.commands.artifacts.run_repo_bash", return_value=0)
def test_build_calls_run_repo_bash(mock_run, tmp_path: Path) -> None:
    ...
    assert mock_run.call_args[0][1] == "runtimes/rt-a/build.sh"
```

Update each assertion that read `mock_run.call_args[0][1]` so it reads the right positional now — the first arg is `Settings`, the second is the script path. Replace those assertions with:

```python
    args, _ = mock_run.call_args
    assert args[1] == "runtimes/rt-a/build.sh"  # or models/md-a/pull.sh in pull test
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/integration/test_cli_milestone2.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/llm_cli/commands/artifacts.py tests/integration/test_cli_milestone2.py
git commit -m "refactor(artifacts): pass Settings to run_repo_bash"
```

---

### Task 21: Update `commands/specs.py` to read `data_root` from `Settings`

**Files:**
- Modify: `src/llm_cli/commands/specs.py`

- [ ] **Step 1: Replace the `_gather_block` function**

In `src/llm_cli/commands/specs.py`, replace the `_gather_block` function with:

```python
from llm_cli.core.settings import (
    MissingSettingError,
    load_settings,
    resolve,
)


def _gather_block(repo: Path) -> str:
    data_root = "not detected"
    try:
        data_root = resolve(load_settings()).data_root.as_posix()
    except (MissingSettingError, ValueError):
        pass
    specs = detect_all(repo_root=repo.resolve().as_posix(), data_root=data_root)
    return render_specs_block(specs, generated_at=_utcnow_iso())
```

Remove the now-unused import `from llm_cli.core.paths import load_paths`.

- [ ] **Step 2: Run the specs tests**

Run: `pytest tests/integration/test_cli_specs.py -v`
Expected: PASS (these tests were already migrated in Task 18 to write a settings file).

- [ ] **Step 3: Commit**

```bash
git add src/llm_cli/commands/specs.py
git commit -m "refactor(specs): read data_root from Settings (drop paths.yaml)"
```

---

## Phase 6 — Cleanup

### Task 22: Delete `core/paths.py` and its tests

**Files:**
- Delete: `src/llm_cli/core/paths.py`, `tests/unit/test_paths.py`

- [ ] **Step 1: Verify nothing imports `core.paths`**

Run: `grep -R "from llm_cli.core.paths" src tests || echo OK`
Expected: only `OK` (no matches). If matches appear, fix them — they belong to earlier tasks.

- [ ] **Step 2: Delete**

```bash
git rm src/llm_cli/core/paths.py tests/unit/test_paths.py
```

- [ ] **Step 3: Run the full suite**

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove core/paths.py (superseded by core/settings.py)"
```

---

### Task 23: Delete `paths.yaml`

**Files:**
- Delete: `paths.yaml`

- [ ] **Step 1: Verify nothing reads it**

Run: `grep -R "paths.yaml" src tests || echo OK`
Expected: only `OK`.

- [ ] **Step 2: Delete**

```bash
git rm paths.yaml
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove paths.yaml (settings live in ~/.config/llm/)"
```

---

## Phase 7 — install.sh

### Task 24: Update `install.sh` to auto-invoke `llm setup`

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Replace `install.sh`**

```bash
#!/usr/bin/env bash
# Install the LocalLLM CLI into a venv and expose `llm` on PATH.
# Run inside WSL2 from the repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Where the CLI venv lives. Honors $LLM_DATA_ROOT or falls back to ~/llm.
data_root="${LLM_DATA_ROOT:-$HOME/llm}"
venv_dir="$data_root/.cli-venv"

echo "==> Creating venv at $venv_dir"
mkdir -p "$data_root"
"$PYTHON" -m venv "$venv_dir"

echo "==> Installing localllm-cli (editable)"
"$venv_dir/bin/pip" install --upgrade pip
"$venv_dir/bin/pip" install -e "$REPO_ROOT"

local_bin="$HOME/.local/bin"
mkdir -p "$local_bin"
ln -sf "$venv_dir/bin/llm" "$local_bin/llm"

config_path="${XDG_CONFIG_HOME:-$HOME/.config}/llm/config.yaml"
if [ -z "${LLM_SKIP_SETUP:-}" ] && [ ! -f "$config_path" ]; then
  echo
  echo "==> Running first-time setup"
  ( cd "$REPO_ROOT" && "$venv_dir/bin/llm" setup )
fi

echo
echo "Installed. Make sure ~/.local/bin is on your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Next steps:"
echo "  llm settings show   # confirm settings"
echo "  llm doctor          # verify external prerequisites"
echo "  llm list            # list runtimes, models, configs, benchmarks"
```

- [ ] **Step 2: Smoke check the script syntax**

Run: `bash -n install.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat(install): auto-invoke `llm setup` on first install"
```

---

## Phase 8 — Docs

### Task 25: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the "Getting started" section** with this exact markdown (the outer fence is four backticks so the inner bash fence renders literally):

`````markdown
## Getting started (first time)

Inside WSL2:

```bash
# 1. Verify external prerequisites
cat requirements.md
# (or after install:) llm doctor

# 2. Install the CLI into a venv and run first-time setup
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # if not already

# 3. Inspect settings (settings live at ~/.config/llm/config.yaml)
llm settings show

# 4. Document the machine
llm specs
```
`````

- [ ] **Step 2: Replace the CLI commands table** with:

```markdown
## CLI commands (Milestone 1–2)

| Command | Purpose |
|---|---|
| `llm setup` | Interactive first-time configurator. Writes `~/.config/llm/config.yaml`, creates data-root subdirectories. Re-runnable. |
| `llm setup --default` | Non-interactive: use built-in defaults for every key. |
| `llm settings show` | Print settings file path, stored contents, and resolved view. |
| `llm settings env` | Print `export LLM_*=...` lines for `eval "$(llm settings env)"`. |
| `llm settings edit <key>` | Interactive prompt to update one key. |
| `llm settings edit <key> --default` | Reset key to its built-in default (`data_root`) or remove the override (`runtimes_dir`/`models_dir`/`cache_dir`). |
| `llm specs` | Regenerate the auto block in `specs.md` |
| `llm specs --check` | Exit nonzero if `specs.md` differs from current detection |
| `llm specs --print` | Print detection without writing |
| `llm doctor` | Run all checks from `requirements.yaml` |
| `llm doctor render-requirements` | Regenerate `requirements.md` from `requirements.yaml` |
| `llm list` | List runtimes, models, configs, and benchmarks |
| `llm config show <id>` | Print a single launch config (with `${data_root}` expanded in `serve.env`) |
| `llm config validate` | Validate every `configs/*.yaml` against manifests and script layout |
| `llm build <runtime-id>` | Run `runtimes/<id>/build.sh` via WSL bash with `LLM_*` env injected |
| `llm pull <model-id>` | Run `models/<id>/pull.sh` via WSL bash with `LLM_*` env injected |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): replace init flow with setup + settings"
```

---

### Task 26: Update `docs/repo-conventions.md`

**Files:**
- Modify: `docs/repo-conventions.md`

- [ ] **Step 1: Replace the "Root files" table row for `paths.yaml`**

Find the row mentioning `paths.yaml` and replace with:

```markdown
| `~/.config/llm/config.yaml` | Per-machine settings (managed via `llm settings ...`); not in the repo |
```

- [ ] **Step 2: Add a "Settings vs configs" callout**

Below the table, add:

```markdown
## Settings vs configs

Two namespaces, intentionally separate:

- **`llm settings ...`** edits `~/.config/llm/config.yaml` (where data lives on this machine, where the repo is, etc.).
- **`llm config show/validate`** operates on `configs/*.yaml` (launch units pairing a runtime + model + serve block).

For manual bash, `eval "$(llm settings env)"` injects `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, `LLM_CACHE` into the current shell.
```

- [ ] **Step 3: Commit**

```bash
git add docs/repo-conventions.md
git commit -m "docs(conventions): describe settings/config namespace split"
```

---

### Task 27: Update `docs/add-a-runtime.md` and `docs/add-a-model.md`

**Files:**
- Modify: `docs/add-a-runtime.md`
- Modify: `docs/add-a-model.md`

- [ ] **Step 1: In `add-a-runtime.md`**

Replace any mention of `llm init` and `.llm-env` with this exact markdown (four-backtick outer fences let the inner triple-backticks render):

`````markdown
The CLI injects `LLM_DATA_ROOT`, `LLM_REPO_ROOT`, `LLM_RUNTIMES`, `LLM_MODELS`, and `LLM_CACHE` into bash every time it spawns one. For ad-hoc shell use, run:

```bash
eval "$(llm settings env)"
bash runtimes/my-runtime/build.sh
```
`````

Replace the "Build artifacts" step with:

`````markdown
## 5. Build artifacts

```bash
llm setup           # once per machine, if not already done
llm build my-runtime
```
`````

- [ ] **Step 2: In `add-a-model.md`**

Same substitutions for the model side:

- Replace `llm init` with `llm setup` in the "Pull weights" section.
- Replace any `.llm-env` references with `eval "$(llm settings env)"`.

- [ ] **Step 3: Commit**

```bash
git add docs/add-a-runtime.md docs/add-a-model.md
git commit -m "docs(howto): replace init/.llm-env with setup + settings env"
```

---

### Task 28: Add pointer in the original scaffolding design

**Files:**
- Modify: `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md`

- [ ] **Step 1: Insert a note near the top (right after the date/status header)**

```markdown
> **Updated 2026-05-17:** the `paths.yaml` / `llm init` / `.llm-env` mechanics
> in this document are superseded by the settings & setup redesign — see
> [`2026-05-17-settings-and-setup-redesign.md`](2026-05-17-settings-and-setup-redesign.md).
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md
git commit -m "docs(spec): point original scaffolding design at redesign"
```

---

## Phase 9 — Smoke test

### Task 29: End-to-end WSL smoke test

**Files:** none modified — this is a manual verification.

- [ ] **Step 1: Reinstall**

Run (in WSL):

```bash
rm -rf ~/.config/llm
cd /mnt/c/Private/Projects/LocalLLM
./install.sh
```

Expected: `install.sh` runs, then `llm setup` prompts for `data_root` (default `~/llm`) and layout (default Y). After answering through, `~/.config/llm/config.yaml` exists and `~/llm/{runtimes,models,cache}` are created.

- [ ] **Step 2: Inspect settings**

```bash
export PATH="$HOME/.local/bin:$PATH"
llm settings show
```

Expected output: file path is `~/.config/llm/config.yaml`; `data_root` and `repo_root` are present; resolved view shows all five keys.

- [ ] **Step 3: Env round-trip**

```bash
eval "$(llm settings env)"
echo "$LLM_DATA_ROOT $LLM_REPO_ROOT $LLM_RUNTIMES"
```

Expected: prints the three resolved paths separated by spaces.

- [ ] **Step 4: Build + pull**

```bash
llm build stub-runtime
llm pull stub-model
test -f "$LLM_RUNTIMES/stub-runtime/.built-stub" && echo build-ok
test -f "$LLM_MODELS/stub-model/README.txt" && echo pull-ok
```

Expected: both `*-ok` lines print; the artifacts are under your `data_root`.

- [ ] **Step 5: Test from outside the repo**

```bash
cd /tmp
llm list
```

Expected: `llm list` still works because `repo_root` is now resolved from settings rather than cwd.

- [ ] **Step 6: Edit + reset**

```bash
llm settings edit data_root --default
llm settings show
```

Expected: stored `data_root` is back to `~/llm`.

- [ ] **Step 7: Commit nothing**

This task changes no files in the repo. If everything is green, the redesign is done. Note any anomalies in the conversation; do not commit.

---

## Done

When all tasks above are checked off, the redesign matches `docs/superpowers/specs/2026-05-17-settings-and-setup-redesign.md` and the CLI surface is:

- `llm setup`, `llm setup --default`
- `llm settings show / env / edit [--default]`
- `llm specs`, `llm doctor`, `llm list`, `llm config show/validate`, `llm build`, `llm pull` (unchanged behavior, new internals)
