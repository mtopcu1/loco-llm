# Install, Update & Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship public curl install, semver releases, and `llm update` for non-git users while keeping the existing git editable dev install.

**Architecture:** Read-only release tarball (wheel + official `runtimes/`) lives under `~/.local/share/localllm/releases/{version}/` with a `current` symlink. User configs move to `~/llm/configs/`. Settings gain `install.kind` (`bundle` | `source`); path helpers (`scaffold_root()`, `configs_root()`) replace hard-coded `repo_root()` / `repo/configs`. Version from hatch-vcs; updates fetch `releases/stable.json`.

**Tech Stack:** Python 3.11+, hatchling + hatch-vcs, httpx, typer, pytest, GitHub Actions, bash.

**Spec:** `docs/superpowers/specs/2026-05-18-install-update-versioning-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | hatch-vcs dynamic version |
| `src/llm_cli/__init__.py` | Re-export `__version__` from metadata helper |
| `src/llm_cli/version.py` | `package_version()` via importlib.metadata |
| `src/llm_cli/core/settings.py` | `InstallInfo`, bundle/source resolution, `configs_dir` |
| `src/llm_cli/core/scaffold.py` | `scaffold_root()`, `configs_root()`, `install_kind()` |
| `src/llm_cli/core/semver.py` | Parse/compare semver for update checks |
| `src/llm_cli/core/release_manifest.py` | Fetch/parse `stable.json` |
| `src/llm_cli/core/bundle_install.py` | Download tarball, verify sha256, extract, symlink `current`, pip install wheel |
| `src/llm_cli/commands/update.py` | `llm update` / `--check` / `--version` |
| `scripts/build-release.sh` | Assemble release tarball locally / in CI |
| `scripts/install.sh` | Public curl installer |
| `scripts/install-dev.sh` | Contributor editable install (today's `install.sh`) |
| `.github/workflows/release.yml` | Tag → test → build → GitHub Release → update `stable.json` |
| `releases/stable.json` | Latest stable pointer (updated by CI) |
| `templates/configs/` | Example configs copied into release bundle |

Commands to refactor (`repo_root()` → `scaffold_root()` for manifests; config paths → `configs_root()`):

- `config_cmd.py`, `list_cmd.py`, `serve.py`, `runtime_cmd.py`, `advisor.py`, `doctor.py`, `lifecycle_cmds.py`, `specs.py`, `chain.py`

---

## Task 1: Dynamic versioning (hatch-vcs)

**Files:**
- Modify: `pyproject.toml`
- Create: `src/llm_cli/version.py`
- Modify: `src/llm_cli/__init__.py`
- Modify: `tests/integration/test_cli_help.py`

- [ ] **Step 1: Add hatch-vcs to pyproject.toml**

In `[project]` replace static version:

```toml
dynamic = ["version"]

[tool.hatch.version]
source = "vcs"

[tool.hatch.build.hooks.vcs]
version-file = "src/llm_cli/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/llm_cli"]
```

Add to `[build-system].requires`: `"hatch-vcs"`.

Remove `version = "0.2.0"` from `[project]`.

- [ ] **Step 2: Create version helper**

Create `src/llm_cli/version.py`:

```python
"""Installed package version."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    try:
        return version("localllm-cli")
    except PackageNotFoundError:
        try:
            from llm_cli._version import __version__
        except ImportError:
            return "0.0.0+unknown"
        return __version__
```

Update `src/llm_cli/__init__.py`:

```python
from llm_cli.version import package_version

__version__ = package_version()
```

- [ ] **Step 3: Tag repo so dev builds resolve**

Run: `git tag v0.2.0` (if not already tagged at current release baseline).

- [ ] **Step 4: Update version test**

In `tests/integration/test_cli_help.py`, change assertion to not hard-code `0.2.0`:

```python
from llm_cli.version import package_version

def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert package_version() in result.stdout
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/integration/test_cli_help.py::test_version_flag_prints_version -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/llm_cli/version.py src/llm_cli/__init__.py tests/integration/test_cli_help.py
git commit -m "feat: derive CLI version from git tags via hatch-vcs"
```

---

## Task 2: Semver compare utility

**Files:**
- Create: `src/llm_cli/core/semver.py`
- Create: `tests/unit/test_semver.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_semver.py`:

```python
import pytest

from llm_cli.core.semver import compare_versions, parse_version


def test_parse_version_simple() -> None:
    assert parse_version("0.2.1") == (0, 2, 1)


def test_parse_version_strips_v_prefix() -> None:
    assert parse_version("v1.0.0") == (1, 0, 0)


def test_compare_versions_newer() -> None:
    assert compare_versions("0.2.0", "0.2.1") == -1


def test_compare_versions_equal() -> None:
    assert compare_versions("0.2.0", "0.2.0") == 0


def test_compare_versions_older() -> None:
    assert compare_versions("0.3.0", "0.2.9") == 1


def test_parse_version_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_version("not-a-version")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_semver.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement semver.py**

Create `src/llm_cli/core/semver.py`:

```python
"""Minimal semver compare for release/update checks (major.minor.patch only)."""
from __future__ import annotations

import re

_VERSION_RE = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def parse_version(raw: str) -> tuple[int, int, int]:
    m = _VERSION_RE.match(raw.strip())
    if not m:
        raise ValueError(f"invalid semver: {raw!r}")
    return int(m.group("major")), int(m.group("minor")), int(m.group("patch"))


def compare_versions(left: str, right: str) -> int:
    """Return -1 if left < right, 0 if equal, 1 if left > right."""
    a = parse_version(left)
    b = parse_version(right)
    if a < b:
        return -1
    if a > b:
        return 1
    return 0
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_semver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/semver.py tests/unit/test_semver.py
git commit -m "feat: add semver parse and compare helpers"
```

---

## Task 3: Extended settings (bundle vs source)

**Files:**
- Modify: `src/llm_cli/core/settings.py`
- Modify: `tests/unit/test_settings.py`

- [ ] **Step 1: Write failing bundle-mode test**

Add to `tests/unit/test_settings.py`:

```python
def test_resolve_bundle_mode() -> None:
    out = resolve(
        {
            "data_root": "/dr",
            "install_root": "/opt/localllm/current/bundle",
            "configs_dir": "/dr/configs",
            "install": {
                "kind": "bundle",
                "venv": "/opt/localllm/venv",
                "channel": "stable",
                "version": "0.2.0",
                "releases_dir": "/opt/localllm/releases",
            },
        }
    )
    assert out.install_kind == "bundle"
    assert out.scaffold_root == Path("/opt/localllm/current/bundle")
    assert out.configs_dir == Path("/dr/configs")
    assert out.repo_root is None
    assert out.install is not None
    assert out.install.version == "0.2.0"


def test_resolve_legacy_source_mode_without_install_block() -> None:
    out = resolve({"data_root": "/dr", "repo_root": "/repo"})
    assert out.install_kind == "source"
    assert out.scaffold_root == Path("/repo")
    assert out.configs_dir == Path("/repo/configs")
    assert out.repo_root == Path("/repo")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_settings.py::test_resolve_bundle_mode -v`
Expected: FAIL

- [ ] **Step 3: Extend settings.py**

Add dataclasses and extend `Settings`:

```python
@dataclass(frozen=True)
class InstallInfo:
    kind: str
    venv: Path | None
    channel: str
    version: str | None
    releases_dir: Path | None


@dataclass(frozen=True)
class Settings:
    data_root: Path
    install_kind: str
    scaffold_root: Path
    configs_dir: Path
    runtimes_dir: Path
    models_dir: Path
    cache_dir: Path
    repo_root: Path | None
    install: InstallInfo | None
```

Add to `KEY_REGISTRY`:

```python
"install_root": {"default": None, "required": False, "kind": "path"},
"configs_dir": {"default": None, "required": False, "kind": "path"},
```

Replace `load_settings` / `save_settings` validation:

- Top-level keys must be in `KEY_REGISTRY` **or** equal `install` (nested mapping).
- `install` sub-keys allowed: `kind`, `venv`, `channel`, `version`, `releases_dir` (all strings).

Update `resolve()`:

```python
def _parse_install(raw: dict[str, str] | None) -> InstallInfo | None:
    if not raw:
        return None
    kind = raw.get("kind", "source")
    return InstallInfo(
        kind=kind,
        venv=_expand(raw["venv"]) if raw.get("venv") else None,
        channel=raw.get("channel", "stable"),
        version=raw.get("version"),
        releases_dir=_expand(raw["releases_dir"]) if raw.get("releases_dir") else None,
    )


def resolve(values: dict[str, Any]) -> Settings:
    # ... data_root as today ...
    install = _parse_install(values.get("install") if isinstance(values.get("install"), dict) else None)
    install_kind = install.kind if install else "source"

    if install_kind == "bundle":
        install_root_raw = values.get("install_root")
        if not install_root_raw:
            raise MissingSettingError("install_root is not configured for bundle install")
        scaffold_root = _expand(install_root_raw)
        configs_dir = _expand(values.get("configs_dir") or str(data_root / "configs"))
        repo_root = None
    else:
        repo_root_raw = values.get("repo_root")
        if not repo_root_raw:
            raise MissingSettingError(
                "repo_root is not configured; run `llm setup` from inside the repo"
            )
        repo_root = _expand(repo_root_raw)
        scaffold_root = repo_root
        configs_dir = _expand(values.get("configs_dir") or str(repo_root / "configs"))

    return Settings(
        data_root=data_root,
        install_kind=install_kind,
        scaffold_root=scaffold_root,
        configs_dir=configs_dir,
        runtimes_dir=_dir("runtimes_dir", "runtimes"),
        models_dir=_dir("models_dir", "models"),
        cache_dir=_dir("cache_dir", "cache"),
        repo_root=repo_root,
        install=install,
    )
```

Update `ensure_data_dirs` to also mkdir `configs_dir`.

Fix existing tests: `Settings(...)` constructor calls need new fields; `test_settings_dataclass_has_expected_fields` updated accordingly.

- [ ] **Step 4: Run settings tests**

Run: `python -m pytest tests/unit/test_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/settings.py tests/unit/test_settings.py
git commit -m "feat: add bundle vs source settings resolution"
```

---

## Task 4: Scaffold path helpers

**Files:**
- Create: `src/llm_cli/core/scaffold.py`
- Modify: `src/llm_cli/core/repo.py`
- Create: `tests/unit/test_scaffold.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_scaffold.py`:

```python
from pathlib import Path

import pytest

from llm_cli.core.scaffold import configs_root, scaffold_root
from llm_cli.core.settings import MissingSettingError


def test_scaffold_root_source_mode(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = tmp_path / "cfg" / "llm" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(f"data_root: {tmp_path / 'dr'}\nrepo_root: {repo}\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert scaffold_root() == repo.resolve()
    assert configs_root() == (repo / "configs").resolve()


def test_scaffold_root_bundle_mode(monkeypatch, tmp_path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    cfg = tmp_path / "cfg" / "llm" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        f"""data_root: {tmp_path / 'dr'}
install_root: {bundle}
configs_dir: {tmp_path / 'dr' / 'configs'}
install:
  kind: bundle
  venv: {tmp_path / 'venv'}
  channel: stable
  version: "0.2.0"
  releases_dir: {tmp_path / 'releases'}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert scaffold_root() == bundle.resolve()
    assert configs_root() == (tmp_path / "dr" / "configs").resolve()
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/unit/test_scaffold.py -v`

- [ ] **Step 3: Implement scaffold.py**

Create `src/llm_cli/core/scaffold.py`:

```python
"""Resolve scaffold (manifest) and config directory paths."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.settings import MissingSettingError, load_settings, resolve


class ScaffoldRootMissing(RuntimeError):
    """Raised when scaffold_root is missing or invalid."""


def _resolved_settings():
    try:
        return resolve(load_settings())
    except MissingSettingError as exc:
        raise ScaffoldRootMissing(str(exc)) from exc


def scaffold_root() -> Path:
    settings = _resolved_settings()
    root = settings.scaffold_root
    if not root.is_dir():
        raise ScaffoldRootMissing(
            f"scaffold root {root} is not a directory; "
            "re-run install or fix settings"
        )
    return root.resolve()


def configs_root() -> Path:
    settings = _resolved_settings()
    root = settings.configs_dir
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()
```

Update `src/llm_cli/core/repo.py` to delegate (keep backward compat):

```python
def repo_root() -> Path:
    """Return scaffold root in source mode; alias for legacy callers."""
    from llm_cli.core.scaffold import scaffold_root
    return scaffold_root()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_scaffold.py tests/unit/test_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/scaffold.py src/llm_cli/core/repo.py tests/unit/test_scaffold.py
git commit -m "feat: add scaffold_root and configs_root path helpers"
```

---

## Task 5: Config discovery and commands use configs_root

**Files:**
- Modify: `src/llm_cli/core/registry.py`
- Modify: `src/llm_cli/commands/config_cmd.py`
- Modify: `tests/unit/test_registry.py` (or add integration test)

- [ ] **Step 1: Write failing test for external configs dir**

Add to `tests/unit/test_registry.py`:

```python
def test_discover_configs_from_custom_dir(tmp_path) -> None:
    configs = tmp_path / "my-configs"
    configs.mkdir()
    (configs / "stub-runtime__default.yaml").write_text(
        "id: stub-runtime__default\nruntime: stub-runtime\n"
        "serve:\n  host: 127.0.0.1\n  port: 8080\n  params: {}\n",
        encoding="utf-8",
    )
    found = registry.discover_configs(configs)
    assert len(found) == 1
    assert found[0].id == "stub-runtime__default"
```

- [ ] **Step 2: Change discover_configs signature**

In `registry.py`, change:

```python
def discover_configs(configs_dir: Path) -> list[ConfigRecord]:
    root = configs_dir
    ...
```

Update `get_config(repo, config_id)` → split params:

```python
def get_config(configs_dir: Path, config_id: str) -> ConfigRecord | None:
    for c in discover_configs(configs_dir):
        ...
```

Grep all `discover_configs(` and `get_config(` call sites; pass `configs_root()` from commands, `scaffold_root()` for runtime manifests.

- [ ] **Step 3: Update config_cmd.py**

Replace `repo = repo_root()` with:

```python
from llm_cli.core.scaffold import configs_root, scaffold_root

scaffold = scaffold_root()
configs = configs_root()
```

Change paths:
- `repo / "configs" / f"{cid}.yaml"` → `configs / f"{cid}.yaml"`
- `registry.get_runtime_manifest(scaffold, ...)` (unchanged pattern, variable rename)
- `append_history(scaffold, ...)` — history stays tied to scaffold root if `state/` lives there in dev; in bundle mode history goes to data_root — check `append_history` and pass `settings.data_root / "state"` or keep using scaffold only in source mode. **Decision:** pass `resolve(load_settings()).data_root` for history in bundle mode; update `append_history` callers in config_cmd to use `settings.data_root` for bundle installs (read `lifecycle.py` — if history is under repo `state/`, bundle mode should use `data_root/state/`). Add `state_root(settings)` helper if needed.

- [ ] **Step 4: Update list_cmd, serve, advisor, doctor, lifecycle, specs, chain**

Mechanical replace:
- Runtime/benchmark discovery: `scaffold_root()`
- Config discovery: `configs_root()`
- `Settings.repo_root` → `settings.scaffold_root` for env injection (`LLM_REPO_ROOT` keeps name but points at bundle root in bundle mode — document in spec)

- [ ] **Step 5: Run targeted tests**

Run: `python -m pytest tests/unit/test_registry.py tests/integration/test_cli_config_setup.py -q`
Fix failures.

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/core/registry.py src/llm_cli/commands/*.py src/llm_cli/core/chain.py
git commit -m "refactor: resolve configs from configs_dir and manifests from scaffold_root"
```

---

## Task 6: Release manifest fetch

**Files:**
- Create: `src/llm_cli/core/release_manifest.py`
- Create: `tests/unit/test_release_manifest.py`

- [ ] **Step 1: Write failing test with httpx mock**

```python
import json

import httpx
import pytest

from llm_cli.core.release_manifest import StableManifest, fetch_stable_manifest


def test_fetch_stable_manifest_parses_json(httpx_mock) -> None:
    payload = {
        "channel": "stable",
        "version": "0.2.1",
        "tarball_url": "https://example.com/localllm-0.2.1.tar.gz",
        "sha256": "abc",
        "published_at": "2026-05-18T12:00:00Z",
        "min_python": "3.11",
    }
    httpx_mock.add_response(url="https://example.com/stable.json", json=payload)
    got = fetch_stable_manifest("https://example.com/stable.json")
    assert got == StableManifest(
        channel="stable",
        version="0.2.1",
        tarball_url="https://example.com/localllm-0.2.1.tar.gz",
        sha256="abc",
        published_at="2026-05-18T12:00:00Z",
        min_python="3.11",
    )
```

Add `pytest-httpx` to dev deps if not present, or use `unittest.mock.patch` on `httpx.get`.

- [ ] **Step 2: Implement release_manifest.py**

```python
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class StableManifest:
    channel: str
    version: str
    tarball_url: str
    sha256: str
    published_at: str
    min_python: str


DEFAULT_STABLE_URL = (
    "https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/releases/stable.json"
)


def fetch_stable_manifest(url: str = DEFAULT_STABLE_URL) -> StableManifest:
    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    return StableManifest(
        channel=str(data["channel"]),
        version=str(data["version"]),
        tarball_url=str(data["tarball_url"]),
        sha256=str(data["sha256"]),
        published_at=str(data.get("published_at", "")),
        min_python=str(data.get("min_python", "3.11")),
    )
```

- [ ] **Step 3: Run tests, commit**

```bash
git add src/llm_cli/core/release_manifest.py tests/unit/test_release_manifest.py pyproject.toml
git commit -m "feat: fetch and parse stable release manifest"
```

---

## Task 7: Bundle install core logic

**Files:**
- Create: `src/llm_cli/core/bundle_install.py`
- Create: `tests/unit/test_bundle_install.py`
- Create: `tests/fixtures/release/minimal/` (tiny tarball fixture)

- [ ] **Step 1: Write failing test for sha256 verify + extract layout**

Test uses a pre-built minimal tarball in `tests/fixtures/release/localllm-0.0.1-test.tar.gz` containing:

```
0.0.1-test/VERSION
0.0.1-test/wheel/localllm_cli-0.0.1-test-py3-none-any.whl  (empty zip ok for test)
0.0.1-test/bundle/runtimes/stub-runtime/manifest.yaml
```

Test calls `extract_release(archive, releases_dir, expected_sha256=...)` and asserts directory layout + VERSION file.

- [ ] **Step 2: Implement bundle_install.py**

Key functions:

```python
def sha256_file(path: Path) -> str: ...

def download_file(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)

def extract_release(*, tarball: Path, releases_dir: Path, version: str) -> Path:
    """Extract to releases_dir/version; return that path."""
    target = releases_dir / version
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    shutil.unpack_archive(str(tarball), extract_dir := target.parent)
    # tarball top-level is localllm-{version}/ — rename/move to target
    ...

def activate_release(*, release_dir: Path, current_link: Path) -> None:
    """Atomically repoint current symlink."""
    tmp = current_link.with_name(current_link.name + ".tmp")
    tmp.symlink_to(release_dir)
    tmp.replace(current_link)

def pip_install_wheel(*, venv_python: Path, wheel: Path) -> None:
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--force-reinstall", str(wheel)],
        check=True,
    )
```

- [ ] **Step 3: Build minimal fixture tarball in test setup** (pytest fixture creates it once)

- [ ] **Step 4: Run tests, commit**

```bash
git add src/llm_cli/core/bundle_install.py tests/unit/test_bundle_install.py tests/fixtures/release/
git commit -m "feat: add bundle download, verify, and extract helpers"
```

---

## Task 8: `llm update` command

**Files:**
- Create: `src/llm_cli/commands/update_cmd.py`
- Modify: `src/llm_cli/main.py`
- Create: `tests/integration/test_cli_update.py`

- [ ] **Step 1: Write failing integration test**

```python
def test_update_check_refuses_source_mode(tmp_path, monkeypatch):
    # settings with repo_root only, no install.kind bundle
    ...
    result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 1
    assert "git pull" in result.stdout.lower() or "source" in result.stdout.lower()
```

Second test mocks `fetch_stable_manifest` + bundle install functions, settings in bundle mode, `--check` reports upgrade available.

- [ ] **Step 2: Implement update_cmd.py**

```python
@app.command("update")
def update(
    check: bool = False,
    version: Optional[str] = None,
    channel: str = "stable",
) -> None:
    settings = resolve(load_settings())
    if settings.install_kind != "bundle":
        console.print("[red]error:[/red] dev install detected; run: git pull && pip install -e .")
        raise typer.Exit(code=1)
    current = settings.install.version if settings.install else package_version()
    manifest = fetch_stable_manifest()
    target = version or manifest.version
    if compare_versions(current, target) >= 0:
        console.print(f"already at {current}")
        raise typer.Exit(code=0 if not check else 0)
    if check:
        console.print(f"upgrade available: {current} -> {target}")
        raise typer.Exit(code=1)
    # download, verify sha256, extract, pip install, symlink, update settings install.version
    ...
```

Add helper `update_install_version_in_settings(new_version: str)` that read-modify-writes yaml preserving other keys.

- [ ] **Step 3: Register in main.py**

```python
from llm_cli.commands import update_cmd
app.command("update", help="Upgrade a bundle install to the latest release.")(update_cmd.update)
```

- [ ] **Step 4: Run tests, commit**

```bash
git add src/llm_cli/commands/update_cmd.py src/llm_cli/main.py tests/integration/test_cli_update.py
git commit -m "feat: add llm update command for bundle installs"
```

---

## Task 9: Disable custom runtime wizard in bundle mode

**Files:**
- Modify: `src/llm_cli/commands/runtime_cmd.py`
- Create: `tests/integration/test_cli_runtime_setup.py` (add test)

- [ ] **Step 1: Write failing test**

Bundle settings fixture → invoke `llm runtime setup`, choose custom path → expect exit 1 with message about dev install.

- [ ] **Step 2: Guard in `_runtime_setup_custom` or wizard entry**

```python
from llm_cli.core.settings import load_settings, resolve

def interactive_runtime_setup() -> str | None:
    if resolve(load_settings()).install_kind == "bundle":
        console.print(
            "[red]error:[/red] custom runtimes require a source (git) install.\n"
            "See docs/install.md for contributor setup."
        )
        raise typer.Exit(code=1)
    ...
```

- [ ] **Step 3: Run test, commit**

```bash
git commit -m "feat: block custom runtime wizard in bundle install mode"
```

---

## Task 10: Release build script + templates

**Files:**
- Create: `scripts/build-release.sh`
- Create: `templates/configs/.gitkeep` (copy from `configs/stub-runtime__default.yaml` as template)
- Create: `releases/stable.json` (placeholder for bootstrap)

- [ ] **Step 1: Add templates**

Copy `configs/stub-runtime__default.yaml` → `templates/configs/stub-runtime__default.yaml`.

- [ ] **Step 2: Implement build-release.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?usage: build-release.sh VERSION}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING="$ROOT/dist/localllm-$VERSION"
rm -rf "$STAGING"
mkdir -p "$STAGING/wheel" "$STAGING/bundle/runtimes" "$STAGING/bundle/benchmarks" "$STAGING/bundle/templates/configs"

python -m pip wheel "$ROOT" -w "$STAGING/wheel" --no-deps
cp -a "$ROOT/runtimes/." "$STAGING/bundle/runtimes/"
cp -a "$ROOT/benchmarks/." "$STAGING/bundle/benchmarks/"
cp -a "$ROOT/templates/configs/." "$STAGING/bundle/templates/configs/"
echo "$VERSION" > "$STAGING/VERSION"

# manifest.json + SHA256SUMS
(
  cd "$STAGING"
  find . -type f ! -name SHA256SUMS | sort | xargs sha256sum > SHA256SUMS
)
tar -C "$ROOT/dist" -czf "$ROOT/dist/localllm-$VERSION.tar.gz" "localllm-$VERSION"
echo "built dist/localllm-$VERSION.tar.gz"
```

- [ ] **Step 3: Placeholder stable.json**

```json
{
  "channel": "stable",
  "version": "0.2.0",
  "tarball_url": "https://github.com/mtopcu1/local-llm-scaffold/releases/download/v0.2.0/localllm-0.2.0.tar.gz",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "published_at": "2026-05-18T00:00:00Z",
  "min_python": "3.11"
}
```

Replace sha256 after first real release build.

- [ ] **Step 4: Smoke locally**

Run: `bash scripts/build-release.sh 0.2.0-test`
Expected: tarball under `dist/`

- [ ] **Step 5: Commit**

```bash
git add scripts/build-release.sh templates/ releases/stable.json
git commit -m "chore: add release tarball build script and stable manifest stub"
```

---

## Task 11: Public install script

**Files:**
- Create: `scripts/install.sh`
- Rename: `install.sh` → `scripts/install-dev.sh`
- Modify: `README.md` (dev install path)

- [ ] **Step 1: Move dev installer**

```bash
git mv install.sh scripts/install-dev.sh
```

Update `scripts/install-dev.sh` header comment: "Contributor install from git clone."

Add root `install.sh` shim:

```bash
#!/usr/bin/env bash
echo "For development, run: ./scripts/install-dev.sh" >&2
echo "For public install, see README.md" >&2
exit 1
```

Or delegate: root `install.sh` calls `scripts/install-dev.sh` when `.git` present, else `scripts/install.sh`.

**Decision:** root `install.sh` detects `.git` → dev; otherwise prints pointer. Public script lives at `scripts/install.sh`.

- [ ] **Step 2: Implement scripts/install.sh**

Core variables:

```bash
INSTALL_DIR="${LOCALLLM_INSTALL_DIR:-$HOME/.local/share/localllm}"
VENV="$INSTALL_DIR/venv"
RELEASES_DIR="$INSTALL_DIR/releases"
CURRENT_LINK="$INSTALL_DIR/current"
STABLE_URL="${LOCALLLM_STABLE_URL:-https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/releases/stable.json}"
```

Flow per spec §9: fetch manifest, download tarball, verify sha256, extract, venv, pip install wheel, symlink `current` → `$RELEASES_DIR/$VERSION`, write settings yaml, seed configs from `$CURRENT/bundle/templates/configs/`, symlink `~/.local/bin/llm`, optional setup.

Settings write (preserve existing `data_root` if config exists):

```yaml
data_root: ~/llm
install_root: ~/.local/share/localllm/current/bundle
configs_dir: ~/llm/configs
install:
  kind: bundle
  venv: ~/.local/share/localllm/venv
  channel: stable
  version: "0.2.1"
  releases_dir: ~/.local/share/localllm/releases
```

Use `python3 -c` snippets for json/yaml if `jq` not guaranteed.

- [ ] **Step 3: Manual smoke in WSL**

Run public script against locally built tarball by overriding STABLE_URL and tarball_url to file:// or localhost fixture.

- [ ] **Step 4: Commit**

```bash
git add scripts/install.sh scripts/install-dev.sh install.sh README.md
git commit -m "feat: add public bundle install script; move dev install to scripts/install-dev.sh"
```

---

## Task 12: GitHub Actions release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Add workflow**

```yaml
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install hatch pytest
      - run: pytest -q
      - run: |
          VERSION="${GITHUB_REF_NAME#v}"
          bash scripts/build-release.sh "$VERSION"
      - run: |
          VERSION="${GITHUB_REF_NAME#v}"
          SHA=$(sha256sum "dist/localllm-${VERSION}.tar.gz" | awk '{print $1}')
          python scripts/write-stable-json.py "$VERSION" "$SHA"
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/localllm-*.tar.gz
            dist/localllm-*/wheel/*.whl
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add releases/stable.json
          git diff --staged --quiet || git commit -m "chore: update stable.json for ${GITHUB_REF_NAME}"
          git push
```

- [ ] **Step 2: Add scripts/write-stable-json.py**

Small script that writes `releases/stable.json` with computed tarball URL and sha256.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml scripts/write-stable-json.py
git commit -m "ci: add tag-triggered release workflow"
```

---

## Task 13: Setup and ensure_data_dirs for bundle mode

**Files:**
- Modify: `src/llm_cli/commands/setup.py`
- Modify: `src/llm_cli/core/settings.py` (`ensure_data_dirs`)

- [ ] **Step 1: ensure_data_dirs creates configs_dir**

Already in Task 3; verify `~/llm/configs` created on setup.

- [ ] **Step 2: setup.py skips repo_root in bundle mode**

When `install.kind` is bundle in existing settings, `llm setup --default` only ensures data dirs and prints paths — does not overwrite `install_root`.

When run from dev clone without settings, keep current behavior (writes `repo_root`, `install.kind: source` implicitly).

- [ ] **Step 3: Add test + commit**

```bash
git commit -m "fix: setup respects bundle install settings"
```

---

## Task 14: Documentation

**Files:**
- Create: `docs/install.md`
- Modify: `README.md`

- [ ] **Step 1: Write docs/install.md**

Sections: public install one-liner, `llm update`, directory layout, dev install (`scripts/install-dev.sh`), manual rollback, release tagging for maintainers.

- [ ] **Step 2: Update README Getting started**

```markdown
### Public install (no git)

curl -fsSL https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/scripts/install.sh | bash

### Developer install (git clone)

./scripts/install-dev.sh
```

Add `llm update` to command table.

- [ ] **Step 3: Update spec status to Approved**

In `docs/superpowers/specs/2026-05-18-install-update-versioning-design.md`, set `_Status: Approved`.

- [ ] **Step 4: Commit**

```bash
git add docs/install.md README.md docs/superpowers/specs/2026-05-18-install-update-versioning-design.md
git commit -m "docs: add install and update guide for public and dev paths"
```

---

## Task 15: Full verification

- [ ] **Step 1: Run unit tests**

```bash
python -m pytest tests/unit/test_settings.py tests/unit/test_scaffold.py tests/unit/test_semver.py tests/unit/test_release_manifest.py tests/unit/test_bundle_install.py -v
```

- [ ] **Step 2: Run integration tests**

```bash
python -m pytest tests/integration/test_cli_update.py tests/integration/test_cli_config_setup.py -q
```

- [ ] **Step 3: Run full suite**

```bash
python -m pytest -q
```

- [ ] **Step 4: WSL manual smoke**

1. `bash scripts/build-release.sh 0.2.0-test`
2. Install from local tarball with env overrides
3. `llm --version`, `llm list`, `llm update --check`
4. Dev path: `./scripts/install-dev.sh` still works in git clone

---

## Spec coverage checklist

| Spec § | Task |
|--------|------|
| §5 Layout | Tasks 3, 5, 10, 11 |
| §6 Versioning | Task 1 |
| §7 Release CI | Tasks 10, 12 |
| §8 stable.json | Tasks 6, 10, 12 |
| §9 Install script | Task 11 |
| §10 llm update | Tasks 7, 8 |
| §11 Code changes | Tasks 3–9, 13 |
| §12 Error handling | Tasks 7, 8 (raise with clear messages; no symlink on failure) |
| §13 Testing | All test steps |
| §14 Migration | Task 3 legacy source resolution |
| §15 Docs | Task 14 |
| Non-goals | No PyInstaller, no autoupdate on startup, no Windows native |

---

## Verification commands (quick reference)

```bash
# Dev
./scripts/install-dev.sh
python -m pytest -q

# Release build
bash scripts/build-release.sh 0.2.0-test

# Public install (after release published)
curl -fsSL https://raw.githubusercontent.com/mtopcu1/local-llm-scaffold/main/scripts/install.sh | bash
llm update --check
```
