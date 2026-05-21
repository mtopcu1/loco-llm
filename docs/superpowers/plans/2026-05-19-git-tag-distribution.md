# Git-Tag Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PyPI-based install/update model with a curl-installable git-clone pattern (hermes-agent style), strip the publish pipeline and asset-tarball machinery, and reduce CI to one tests workflow plus a release-please workflow that only tags.

**Architecture:** `scripts/install.sh` clones the repo to `$LOCO_LLM_HOME`, checks out the latest semver tag, creates a uv venv with an editable install, and symlinks `loco` onto `$PATH`. `loco update` does the same dance for updates with re-anchor semantics, plus `--branch`/`--tag`/`--check` flags. CI runs pytest on PRs only. `release-please.yml` opens a release PR; merging it creates the git tag + GitHub Release. No PyPI publishing, no scaffold tarball, no `publish.yml`.

**Tech Stack:** Python 3.11+, Hatchling build backend, GitHub Actions (`googleapis/release-please-action@v4`, `astral-sh/setup-uv@v3`), `uv`, `git`, Conventional Commits.

**Related spec:** `docs/superpowers/specs/2026-05-19-git-tag-distribution-design.md` — full rationale, decisions, and architecture. Section 7 (install), Section 8 (update), Section 13 (burn-down) are the most directly actionable.

---

## Background — what exists today (for the engineer with zero context)

- Repo: `github.com/mtopcu1/loco-llm` (moved from `local-llm-scaffold`). Default branch `main`. Maintainer on Windows; product targets WSL2/Linux/macOS.
- Python Typer CLI in `src/llm_cli/`. Entry point `loco` defined in `pyproject.toml` `[project.scripts]`.
- Today's install: `scripts/install.sh` does `pipx install loco-llm-cli==<pinned>` from PyPI, then `loco update --scaffold-only` to download a scaffold tarball. We're throwing this away.
- Today's update: `src/llm_cli/commands/update_cmd.py` upgrades the pipx wheel + the scaffold tarball. We're throwing this away too.
- Today's CI: `.github/workflows/ci.yml` (pytest matrix + build-check), `release-please.yml` (release PR + chained publish + version sync check), `publish.yml` (manual fallback). All three need rewriting/removal.
- Conventional commits: enforced socially via `.cursor/rules/conventional-commits.mdc` + `CONTRIBUTING.md`. Release-please drives version bumps in `pyproject.toml` and `src/llm_cli/__init__.py` based on commit messages.
- Current version: `0.3.2` (per `pyproject.toml` and `__init__.py`).
- Branch protection on `main` requires `test (3.11)`, `test (3.12)`, `build-check`. These check names go away in this plan; protection will need to be re-pointed at the new single `test` check (manual step in Task 11).

## File map

**Create:**
- `tests/unit/test_scaffold_home.py` — replacement for parts of `test_scaffold.py` covering `scaffold_root()` returning `LOCO_LLM_HOME`/git toplevel.

**Modify:**
- `src/llm_cli/core/scaffold.py` — repurpose `scaffold_root()` to return `LOCO_LLM_HOME` or git toplevel.
- `src/llm_cli/commands/update_cmd.py` — rewrite with git-based re-anchor flow.
- `src/llm_cli/commands/doctor.py` — add off-tag warning check.
- `src/llm_cli/main.py` — `--version` formatting with branch/sha suffix.
- `scripts/install.sh` — rewrite as curl-installable clone + uv editable install.
- `.github/workflows/ci.yml` — collapse to one PR-only test job using uv.
- `.github/workflows/release-please.yml` — strip to just the release-please action; no publish/check jobs.
- `tests/unit/test_workflows.py` — update to match new workflow shapes; drop publish tests.
- `tests/unit/test_update_cmd.py` — rewrite for git-based update behavior.
- `tests/unit/test_scaffold.py` — strip tests for deleted helpers.
- `tests/integration/test_cli_help.py` — update if `--version` format changes.
- `pyproject.toml` — drop `twine` from `[dev]`; keep `build` (optional).
- `README.md` — replace install/update sections; drop pipx mentions.
- `CONTRIBUTING.md` — drop PyPI section; keep conventional commits.
- `docs/RELEASE_SETUP.md` — slim to Actions PR creation + branch protection note.

**Delete:**
- `.github/workflows/publish.yml`
- `scripts/install-dev.sh`
- `scripts/migrate-from-v0.2.sh`
- `scripts/check_release_versions.py`
- `src/llm_cli/core/update_check.py`
- `src/llm_cli/core/scaffold_update.py`
- `src/llm_cli/core/scaffold_drift.py`
- `tests/unit/test_update_check.py`
- `tests/unit/test_scaffold_update.py`
- `tests/unit/test_scaffold_drift.py`

**Untouched:**
- All runtime/model/config/serve/doctor (except doctor.py modification)/setup/settings/lifecycle code under `src/llm_cli/`.
- `runtimes/`, `configs/`, `benchmarks/`.
- `release-please-config.json`, `.release-please-manifest.json`.
- `.cursor/rules/conventional-commits.mdc`.
- All integration tests other than `test_cli_help.py`.

---

## Manual prerequisites (do these once, before Task 1)

- [ ] **MP1: Close PR #9.**

  PR #9 (`ci/release-please-fast-path` → main) adds an inline version-sync check that this plan deletes. Close without merging:

  ```bash
  gh pr close 9 --repo mtopcu1/loco-llm --comment "Superseded by feat/git-tag-distribution; throwing away the PyPI flow."
  git push origin --delete ci/release-please-fast-path
  ```

- [ ] **MP2: Verify `uv` is available locally.**

  ```bash
  uv --version
  ```

  Expected: `uv 0.4.x` or newer. If missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **MP3: Note current branch protection contexts** (for re-pointing in Task 11).

  ```bash
  gh api repos/mtopcu1/loco-llm/branches/main/protection --jq ".required_status_checks.contexts"
  ```

  Expected: `["test (3.11)","test (3.12)","build-check"]`. After this plan, the only required context will be `test`.

---

## Task 1: Repurpose `scaffold.py` to return `LOCO_LLM_HOME`

**Files:**
- Modify: `src/llm_cli/core/scaffold.py`
- Modify: `tests/unit/test_scaffold.py`
- Create: `tests/unit/test_scaffold_home.py`

In the new model, the "scaffold dir" is the git clone itself. `scaffold_root()` resolves to (in priority order): `$LOCO_LLM_HOME` env var → `configured_repo_root()` from settings → git toplevel from the running module's location. Remove tarball-specific helpers (`scaffold_dir`, `default_scaffold_dir`, `read_scaffold_version`).

- [ ] **Step 1: Write the failing test for env-var override.**

  Create `tests/unit/test_scaffold_home.py`:

  ```python
  """Tests for the LOCO_LLM_HOME-based scaffold_root resolution."""
  from __future__ import annotations

  from pathlib import Path

  import pytest

  from llm_cli.core import scaffold


  def test_scaffold_root_uses_loco_llm_home_env_var(tmp_path, monkeypatch):
      monkeypatch.setenv("LOCO_LLM_HOME", str(tmp_path))
      monkeypatch.setattr(scaffold, "configured_repo_root", lambda: None)
      assert scaffold.scaffold_root() == tmp_path.resolve()


  def test_scaffold_root_prefers_configured_repo_root_when_no_env(
      tmp_path, monkeypatch
  ):
      monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
      dev = tmp_path / "dev"
      dev.mkdir()
      monkeypatch.setattr(scaffold, "configured_repo_root", lambda: dev.resolve())
      assert scaffold.scaffold_root() == dev.resolve()


  def test_scaffold_root_falls_back_to_module_git_toplevel(monkeypatch, tmp_path):
      monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
      monkeypatch.setattr(scaffold, "configured_repo_root", lambda: None)
      monkeypatch.setattr(scaffold, "_module_git_toplevel", lambda: tmp_path)
      assert scaffold.scaffold_root() == tmp_path.resolve()


  def test_scaffold_root_raises_when_no_source(monkeypatch):
      monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
      monkeypatch.setattr(scaffold, "configured_repo_root", lambda: None)
      monkeypatch.setattr(scaffold, "_module_git_toplevel", lambda: None)
      with pytest.raises(RuntimeError, match="LOCO_LLM_HOME"):
          scaffold.scaffold_root()
  ```

- [ ] **Step 2: Run tests to confirm they fail.**

  ```bash
  python -m pytest tests/unit/test_scaffold_home.py -q
  ```

  Expected: collection or import error referencing missing helpers / env-var behavior.

- [ ] **Step 3: Rewrite `src/llm_cli/core/scaffold.py`.**

  Replace the file contents with:

  ```python
  """Resolve LOCO_LLM_HOME — the git checkout that is the install root."""
  from __future__ import annotations

  import os
  import subprocess
  from pathlib import Path

  from llm_cli.core.settings import Settings, load_settings


  def _module_git_toplevel() -> Path | None:
      """Best-effort: git toplevel of the directory containing this module."""
      here = Path(__file__).resolve().parent
      try:
          out = subprocess.run(
              ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
              capture_output=True,
              text=True,
              check=True,
              timeout=5,
          )
      except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
          return None
      top = out.stdout.strip()
      return Path(top).resolve() if top else None


  def configured_repo_root() -> Path | None:
      """Dev override: explicit repo_root from settings, if set and valid."""
      values = load_settings()
      raw = values.get("repo_root")
      if not raw:
          return None
      path = Path(raw).expanduser()
      return path.resolve() if path.is_dir() else None


  def scaffold_root() -> Path:
      """Return the git checkout root (LOCO_LLM_HOME, dev override, or git toplevel)."""
      env = os.environ.get("LOCO_LLM_HOME")
      if env:
          return Path(env).expanduser().resolve()
      dev = configured_repo_root()
      if dev is not None:
          return dev
      top = _module_git_toplevel()
      if top is not None:
          return top
      raise RuntimeError(
          "could not resolve scaffold root; set LOCO_LLM_HOME or run from a git checkout"
      )


  def user_assets_root(settings: Settings) -> Path:
      return settings.data_root / "user"


  def user_runtimes_dir(settings: Settings) -> Path:
      return user_assets_root(settings) / "runtimes"


  def user_configs_dir(settings: Settings) -> Path:
      return user_assets_root(settings) / "configs"


  def user_benchmarks_dir(settings: Settings) -> Path:
      return user_assets_root(settings) / "benchmarks"
  ```

- [ ] **Step 4: Strip removed-helper tests from `tests/unit/test_scaffold.py`.**

  Remove every test that references `default_scaffold_dir`, `scaffold_dir`, `read_scaffold_version`, or `xdg_data_home`. Keep tests that exercise `scaffold_root()` with the new contract; if none remain, leave the file with only a module docstring + an `import` smoke test.

- [ ] **Step 5: Run scaffold tests.**

  ```bash
  python -m pytest tests/unit/test_scaffold.py tests/unit/test_scaffold_home.py -q
  ```

  Expected: all pass.

- [ ] **Step 6: Find and fix callers of the removed helpers.**

  ```bash
  rg "default_scaffold_dir|scaffold_dir|read_scaffold_version|xdg_data_home" src tests
  ```

  For each hit outside `core/scaffold.py` and the new test file, replace with `scaffold_root()`. If a caller used `read_scaffold_version()` — those callers are being deleted in Task 2 (they're in `update_cmd.py` and friends); leave them broken for now and Task 2 will remove them.

- [ ] **Step 7: Commit.**

  ```bash
  git add src/llm_cli/core/scaffold.py tests/unit/test_scaffold_home.py tests/unit/test_scaffold.py
  git commit -m "refactor(scaffold): resolve install root via LOCO_LLM_HOME and git toplevel"
  ```

---

## Task 2: Delete obsolete modules and their tests

**Files:**
- Delete: `src/llm_cli/core/update_check.py`, `src/llm_cli/core/scaffold_update.py`, `src/llm_cli/core/scaffold_drift.py`
- Delete: `tests/unit/test_update_check.py`, `tests/unit/test_scaffold_update.py`, `tests/unit/test_scaffold_drift.py`

These modules cover PyPI version fetching, scaffold tarball install/rollback, and CLI-vs-scaffold version drift. None survive the new model. `update_cmd.py` will be broken after this task; Task 3 rewrites it.

- [ ] **Step 1: Confirm what depends on these modules.**

  ```bash
  rg "from llm_cli.core.update_check|from llm_cli.core.scaffold_update|from llm_cli.core.scaffold_drift|scaffold_drift|scaffold_update" src tests
  ```

  Note every hit. Expected callers: `update_cmd.py`, `doctor.py` (drift check), `tests/unit/test_update_cmd.py`, `tests/unit/test_doctor_check.py`. Tasks 3 and 5 fix them.

- [ ] **Step 2: Delete the modules.**

  ```bash
  git rm src/llm_cli/core/update_check.py src/llm_cli/core/scaffold_update.py src/llm_cli/core/scaffold_drift.py
  ```

  Note: if `scaffold_update.py` or `scaffold_drift.py` does not exist in your checkout (some prior PRs may have removed one), skip that path in the `git rm` invocation.

- [ ] **Step 3: Delete the corresponding tests.**

  ```bash
  git rm tests/unit/test_update_check.py tests/unit/test_scaffold_update.py tests/unit/test_scaffold_drift.py
  ```

  Same skip-if-missing caveat.

- [ ] **Step 4: Commit. (Tests will be red across the repo; that's expected.)**

  ```bash
  git commit -m "chore: remove PyPI version check, scaffold tarball install, and drift detection"
  ```

---

## Task 3: Rewrite `loco update` (re-anchor flow + flags)

**Files:**
- Modify: `src/llm_cli/commands/update_cmd.py`
- Modify: `tests/unit/test_update_cmd.py`

The new `update` command operates on the git checkout at `scaffold_root()`. Default behavior: re-anchor to the latest semver tag. Flags: `--branch <name>`, `--tag <vX.Y.Z>`, `--check`. Lifecycle integration (refusing to update while a service runs unless `--restart`) is preserved from the old implementation.

- [ ] **Step 1: Write the failing test for bare update on a clean clone.**

  Replace `tests/unit/test_update_cmd.py` with:

  ```python
  """Tests for git-based loco update."""
  from __future__ import annotations

  import subprocess
  from pathlib import Path

  import pytest
  from typer.testing import CliRunner

  from llm_cli.main import app

  runner = CliRunner()


  def _init_repo(root: Path, tags: list[str], on_branch: str | None = None) -> None:
      """Initialize a fake clone with a sequence of tags and optional branch HEAD."""
      subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
      subprocess.run(
          ["git", "-C", str(root), "config", "user.email", "test@example.com"],
          check=True,
      )
      subprocess.run(
          ["git", "-C", str(root), "config", "user.name", "Test"], check=True
      )
      (root / "pyproject.toml").write_text('[project]\nname = "loco-llm-cli"\n')
      subprocess.run(["git", "-C", str(root), "add", "."], check=True)
      subprocess.run(
          ["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True
      )
      for tag in tags:
          subprocess.run(
              ["git", "-C", str(root), "tag", "-a", tag, "-m", tag], check=True
          )
      if on_branch is not None:
          subprocess.run(
              ["git", "-C", str(root), "checkout", "-q", "-b", on_branch], check=True
          )


  @pytest.fixture
  def fake_clone(tmp_path, monkeypatch):
      root = tmp_path / "loco"
      root.mkdir()
      _init_repo(root, tags=["v0.4.0", "v0.4.1"])
      monkeypatch.setenv("LOCO_LLM_HOME", str(root))
      monkeypatch.setattr(
          "llm_cli.commands.update_cmd._sync_deps", lambda _root: None
      )
      monkeypatch.setattr(
          "llm_cli.commands.update_cmd._fetch_remote", lambda _root, _refspec=None: None
      )
      monkeypatch.setattr(
          "llm_cli.commands.update_cmd._service_running", lambda: False
      )
      return root


  def test_update_bare_already_on_latest_is_noop(fake_clone):
      subprocess.run(
          ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.1"], check=True
      )
      result = runner.invoke(app, ["update"])
      assert result.exit_code == 0
      assert "already on latest stable" in result.stdout.lower()


  def test_update_bare_advances_to_latest_tag(fake_clone):
      subprocess.run(
          ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.0"], check=True
      )
      result = runner.invoke(app, ["update"])
      assert result.exit_code == 0
      assert "updated to v0.4.1" in result.stdout.lower()


  def test_update_bare_reanchors_from_branch(fake_clone):
      subprocess.run(
          ["git", "-C", str(fake_clone), "checkout", "-q", "-b", "hotfix/x"],
          check=True,
      )
      result = runner.invoke(app, ["update"])
      assert result.exit_code == 0
      assert "switching back to latest stable" in result.stdout.lower()
      assert "v0.4.1" in result.stdout


  def test_update_branch_flag_checks_out_branch(fake_clone):
      subprocess.run(
          ["git", "-C", str(fake_clone), "branch", "hotfix/y", "v0.4.0"],
          check=True,
      )
      result = runner.invoke(app, ["update", "--branch", "hotfix/y"])
      assert result.exit_code == 0
      assert "not a stable release" in result.stdout.lower()
      head = subprocess.run(
          ["git", "-C", str(fake_clone), "rev-parse", "--abbrev-ref", "HEAD"],
          capture_output=True,
          text=True,
          check=True,
      ).stdout.strip()
      assert head == "hotfix/y"


  def test_update_tag_flag_pins_to_specific_tag(fake_clone):
      result = runner.invoke(app, ["update", "--tag", "v0.4.0"])
      assert result.exit_code == 0
      assert "v0.4.0" in result.stdout
      head = subprocess.run(
          ["git", "-C", str(fake_clone), "describe", "--tags", "--exact-match"],
          capture_output=True,
          text=True,
          check=True,
      ).stdout.strip()
      assert head == "v0.4.0"


  def test_update_check_flag_exits_nonzero_when_behind(fake_clone):
      subprocess.run(
          ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.0"], check=True
      )
      result = runner.invoke(app, ["update", "--check"])
      assert result.exit_code == 1
      assert "v0.4.0" in result.stdout
      assert "v0.4.1" in result.stdout


  def test_update_check_flag_exits_zero_when_up_to_date(fake_clone):
      subprocess.run(
          ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.1"], check=True
      )
      result = runner.invoke(app, ["update", "--check"])
      assert result.exit_code == 0


  def test_update_refuses_unmanaged_directory(tmp_path, monkeypatch):
      empty = tmp_path / "not-a-clone"
      empty.mkdir()
      monkeypatch.setenv("LOCO_LLM_HOME", str(empty))
      result = runner.invoke(app, ["update"])
      assert result.exit_code != 0
      assert "not a managed install" in result.stdout.lower()
  ```

- [ ] **Step 2: Run the tests; expect import or behavior failures.**

  ```bash
  python -m pytest tests/unit/test_update_cmd.py -q
  ```

  Expected: failures referencing missing imports or unchanged old behavior.

- [ ] **Step 3: Rewrite `src/llm_cli/commands/update_cmd.py`.**

  Replace the file with:

  ```python
  """`loco update` — pull the latest tag (or a chosen ref) into the git checkout."""
  from __future__ import annotations

  import re
  import shutil
  import subprocess
  from pathlib import Path

  import typer
  from rich.console import Console

  from llm_cli.commands import lifecycle_cmds
  from llm_cli.commands import serve as serve_cmd
  from llm_cli.core.lifecycle import read_running, state_root
  from llm_cli.core.lifecycle_status import service_is_running_for_settings
  from llm_cli.core.scaffold import scaffold_root
  from llm_cli.core.settings import load_settings, resolve

  console = Console()

  _SEMVER_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
  _EXPECTED_REMOTE_HOSTS = ("github.com/mtopcu1/loco-llm",)


  def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
      return subprocess.run(
          ["git", "-C", str(root), *args],
          capture_output=True,
          text=True,
          check=check,
      )


  def _is_git_clone(root: Path) -> bool:
      if not (root / ".git").exists():
          return False
      try:
          _run_git(root, "rev-parse", "--is-inside-work-tree")
      except subprocess.CalledProcessError:
          return False
      return True


  def _remote_matches_expected(root: Path) -> bool:
      try:
          out = _run_git(root, "remote", "get-url", "origin")
      except subprocess.CalledProcessError:
          return False
      url = out.stdout.strip()
      return any(host in url for host in _EXPECTED_REMOTE_HOSTS)


  def _fetch_remote(root: Path, refspec: str | None = None) -> None:
      args = ["fetch", "--tags", "--prune", "origin"]
      if refspec:
          args.append(refspec)
      _run_git(root, *args)


  def _list_semver_tags(root: Path) -> list[str]:
      out = _run_git(root, "tag", "--list", "v*")
      tags = [t for t in out.stdout.split() if _SEMVER_TAG.match(t)]

      def key(tag: str) -> tuple[int, int, int]:
          parts = tag[1:].split(".")
          return tuple(int(p) for p in parts)  # type: ignore[return-value]

      return sorted(tags, key=key)


  def _latest_tag(root: Path) -> str | None:
      tags = _list_semver_tags(root)
      return tags[-1] if tags else None


  def _current_state(root: Path) -> dict[str, str | None]:
      """Return {kind, ref, sha} where kind is 'tag' | 'branch' | 'detached'."""
      sha = _run_git(root, "rev-parse", "HEAD").stdout.strip()
      try:
          tag = _run_git(root, "describe", "--tags", "--exact-match", "HEAD").stdout.strip()
          if tag:
              return {"kind": "tag", "ref": tag, "sha": sha}
      except subprocess.CalledProcessError:
          pass
      branch = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
      if branch and branch != "HEAD":
          return {"kind": "branch", "ref": branch, "sha": sha}
      return {"kind": "detached", "ref": None, "sha": sha}


  def _working_tree_dirty(root: Path) -> bool:
      out = _run_git(root, "status", "--porcelain")
      return bool(out.stdout.strip())


  def _checkout(root: Path, ref: str) -> None:
      _run_git(root, "checkout", ref)


  def _ff_pull(root: Path, branch: str) -> None:
      _run_git(root, "pull", "--ff-only", "origin", branch)


  def _sync_deps(root: Path) -> None:
      uv = shutil.which("uv")
      if uv is None:
          console.print(
              "[yellow]warning:[/yellow] `uv` not found on PATH; skipping dep sync. "
              "Install uv and re-run `loco update` to pick up dependency changes."
          )
          return
      subprocess.run([uv, "pip", "install", "-e", str(root)], check=True)


  def _service_running() -> bool:
      settings = resolve(load_settings())
      return service_is_running_for_settings(settings)


  def _maybe_restart_around_update(restart: bool):
      """Context-manager-ish helper returning (saved_record_or_none)."""
      if not _service_running():
          return None
      if not restart:
          console.print(
              "[red]error:[/red] a service is running. Stop it first (`loco stop`) "
              "or pass --restart to stop and re-start it around the update."
          )
          raise typer.Exit(code=1)
      settings = resolve(load_settings())
      saved = read_running(state_root(settings))
      lifecycle_cmds.stop()
      return saved


  def _restore_service(saved) -> None:
      if saved is None:
          return
      serve_cmd.serve_dispatch(
          saved.config_id,
          foreground=saved.mode == "foreground",
          systemd=saved.mode == "systemd",
      )


  def update(
      branch: str | None = typer.Option(
          None,
          "--branch",
          help="Switch to the tip of the given branch (off-mainline; warns).",
      ),
      tag: str | None = typer.Option(
          None,
          "--tag",
          help="Pin to a specific tag (e.g. v0.4.0).",
      ),
      check: bool = typer.Option(
          False,
          "--check",
          help="Report current vs. latest tag and exit 1 if behind. No changes.",
      ),
      restart: bool = typer.Option(
          False,
          "--restart",
          help="Stop a running service before update and re-serve afterward.",
      ),
  ) -> None:
      """Pull the latest tagged release (or a chosen ref) into the local checkout."""
      if sum(bool(x) for x in (branch, tag, check)) > 1:
          console.print(
              "[red]error:[/red] --branch, --tag, and --check are mutually exclusive."
          )
          raise typer.Exit(code=1)

      root = scaffold_root()
      if not _is_git_clone(root):
          console.print(
              f"[red]error:[/red] {root} is not a managed install (no .git). "
              "Reinstall via the install.sh one-liner."
          )
          raise typer.Exit(code=1)
      if not _remote_matches_expected(root):
          console.print(
              f"[red]error:[/red] {root}/.git/config 'origin' does not look like "
              "github.com/mtopcu1/loco-llm. Refusing to update."
          )
          raise typer.Exit(code=1)

      _fetch_remote(root, refspec=branch)

      state = _current_state(root)

      if check:
          latest = _latest_tag(root)
          if latest is None:
              console.print("[yellow]warning:[/yellow] no semver tags on origin.")
              raise typer.Exit(code=0)
          console.print(f"  current: {state['ref'] or state['sha'][:7]}")
          console.print(f"  latest:  {latest}")
          if state["kind"] == "tag" and state["ref"] == latest:
              console.print("Already on latest stable.")
              raise typer.Exit(code=0)
          raise typer.Exit(code=1)

      if branch is not None:
          saved = _maybe_restart_around_update(restart)
          if _working_tree_dirty(root):
              _run_git(root, "stash", "push", "-u", "-m", "llm-update")
              console.print("[yellow]stashed local changes[/yellow]")
          _checkout(root, branch)
          _ff_pull(root, branch)
          _sync_deps(root)
          _restore_service(saved)
          console.print(
              f"[yellow]you are now on branch {branch} — not a stable release.[/yellow] "
              "Run `loco update` to return to the latest stable tag."
          )
          return

      if tag is not None:
          saved = _maybe_restart_around_update(restart)
          if _working_tree_dirty(root):
              _run_git(root, "stash", "push", "-u", "-m", "llm-update")
              console.print("[yellow]stashed local changes[/yellow]")
          _checkout(root, tag)
          _sync_deps(root)
          _restore_service(saved)
          console.print(f"[green]pinned to {tag}.[/green]")
          return

      latest = _latest_tag(root)
      if latest is None:
          console.print(
              "[red]error:[/red] no semver tags on origin; cannot re-anchor. "
              "Use `--branch main` if you intend to track an untagged branch."
          )
          raise typer.Exit(code=1)

      if state["kind"] == "branch":
          console.print(
              f"[yellow]currently on branch {state['ref']}; "
              f"switching back to latest stable tag {latest}.[/yellow]"
          )
      if state["kind"] == "tag" and state["ref"] == latest:
          console.print(f"Already on latest stable ({latest}).")
          return

      saved = _maybe_restart_around_update(restart)
      if _working_tree_dirty(root):
          _run_git(root, "stash", "push", "-u", "-m", "llm-update")
          console.print("[yellow]stashed local changes[/yellow]")
      _checkout(root, latest)
      _sync_deps(root)
      _restore_service(saved)
      console.print(f"[green]updated to {latest}.[/green]")
  ```

- [ ] **Step 4: Run update tests.**

  ```bash
  python -m pytest tests/unit/test_update_cmd.py -q
  ```

  Expected: all pass.

- [ ] **Step 5: Run the full unit test suite to surface remaining breakage.**

  ```bash
  python -m pytest tests/unit -q
  ```

  Expected failures will be in `test_doctor_check.py` (references the deleted scaffold_drift) and possibly `test_workflows.py`. Tasks 4 and 7+ handle those.

- [ ] **Step 6: Commit.**

  ```bash
  git add src/llm_cli/commands/update_cmd.py tests/unit/test_update_cmd.py
  git commit -m "feat!: rewrite loco update as git-tag-based with re-anchor semantics

  BREAKING CHANGE: loco update no longer reads from PyPI or installs a scaffold tarball.
  It operates on the git checkout at LOCO_LLM_HOME and pulls the latest semver tag.
  --branch, --tag, --check flags replace the old --scaffold-only / --cli-only model."
  ```

---

## Task 4: Off-tag warning in `loco doctor` and `--version`

**Files:**
- Modify: `src/llm_cli/commands/doctor.py` (add a quick check)
- Modify: `src/llm_cli/main.py` (`--version` formatting)
- Modify: `tests/unit/test_doctor_check.py` (drop scaffold drift, add off-tag check)
- Modify: `tests/integration/test_cli_help.py` (assert new `--version` shape)

`loco --version` shows the package version with a suffix if HEAD is off-tag. `loco doctor` adds a check that warns if HEAD is not an exact-match tag.

- [ ] **Step 1: Read the current main.py `--version` callback.**

  ```bash
  rg -n "version_callback|--version" src/llm_cli/main.py
  ```

  Locate the callback and its current return string.

- [ ] **Step 2: Write a failing test in `tests/integration/test_cli_help.py`.**

  Add (replacing any prior `--version` test):

  ```python
  def test_version_flag_prints_package_version():
      result = runner.invoke(app, ["--version"])
      assert result.exit_code == 0
      # Format: "llm X.Y.Z" on a tag, "llm X.Y.Z (branch: name)" off-tag.
      assert "llm " in result.stdout.lower()
      from llm_cli import __version__
      assert __version__ in result.stdout
  ```

- [ ] **Step 3: Update the `--version` callback in `src/llm_cli/main.py`.**

  Replace the existing callback (locate via Step 1) with one that, when on a non-tag HEAD, appends ` (branch: <name>)` or ` (detached: <sha7>)`. Use `llm_cli.commands.update_cmd._current_state` if available; otherwise re-implement a 5-line helper to avoid the import cycle. Recommended: small private helper in `main.py` that shells out to `git -C <scaffold_root> describe`/`rev-parse`, swallows errors, and returns just the suffix.

  ```python
  from llm_cli import __version__
  from llm_cli.core.scaffold import scaffold_root

  def _head_suffix() -> str:
      import subprocess
      try:
          root = scaffold_root()
      except RuntimeError:
          return ""
      try:
          tag = subprocess.run(
              ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
              capture_output=True, text=True, check=True, timeout=2,
          ).stdout.strip()
          if tag:
              return ""
      except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
          pass
      try:
          branch = subprocess.run(
              ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
              capture_output=True, text=True, check=True, timeout=2,
          ).stdout.strip()
          if branch and branch != "HEAD":
              return f" (branch: {branch})"
          sha = subprocess.run(
              ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
              capture_output=True, text=True, check=True, timeout=2,
          ).stdout.strip()
          return f" (detached: {sha})" if sha else ""
      except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
          return ""

  def _version_callback(value: bool) -> None:
      if value:
          typer.echo(f"llm {__version__}{_head_suffix()}")
          raise typer.Exit()
  ```

  Wire it as the existing `--version` callback (signature unchanged).

- [ ] **Step 4: Add doctor check for off-tag HEAD.**

  In `src/llm_cli/commands/doctor.py`, find where checks are aggregated (look for the existing `_check_*` helpers or the `run_quick_checks` builder). Add:

  ```python
  def _check_on_release_tag() -> tuple[str, str, str]:
      """Return (id, status, detail) for the head-on-tag check."""
      import subprocess
      from llm_cli.core.scaffold import scaffold_root
      try:
          root = scaffold_root()
      except RuntimeError as exc:
          return ("install-root", "error", str(exc))
      try:
          subprocess.run(
              ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
              capture_output=True, check=True, timeout=2,
          )
          return ("install-channel", "ok", "on a release tag")
      except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
          return (
              "install-channel",
              "warn",
              "not on a release tag — run `loco update` to re-anchor to the latest stable tag",
          )
  ```

  Then add the call site to whatever aggregator already exists. If unsure, search:

  ```bash
  rg -n "run_quick_checks|_check_" src/llm_cli/commands/doctor.py src/llm_cli/core/doctor.py
  ```

  Inject into the list of checks. Match the existing data shape; the snippet above shows the intent — adapt names as the file requires.

- [ ] **Step 5: Update `tests/unit/test_doctor_check.py`.**

  Remove any test that imports/uses the deleted `scaffold_drift` module. Add:

  ```python
  def test_install_channel_check_warns_when_not_on_tag(tmp_path, monkeypatch):
      from llm_cli.commands.doctor import _check_on_release_tag
      monkeypatch.setenv("LOCO_LLM_HOME", str(tmp_path))
      # tmp_path has no .git → treated as "no tag" path
      cid, status, _ = _check_on_release_tag()
      assert cid == "install-channel"
      assert status in {"warn", "error"}
  ```

- [ ] **Step 6: Run targeted tests.**

  ```bash
  python -m pytest tests/integration/test_cli_help.py tests/unit/test_doctor_check.py -q
  ```

  Expected: all pass.

- [ ] **Step 7: Commit.**

  ```bash
  git add src/llm_cli/main.py src/llm_cli/commands/doctor.py tests/integration/test_cli_help.py tests/unit/test_doctor_check.py
  git commit -m "feat(cli): warn when running off a release tag

  loco --version now appends '(branch: X)' or '(detached: sha)' when HEAD is
  not an exact tag match. loco doctor adds an install-channel check that
  warns and points at \`loco update\` to re-anchor."
  ```

---

## Task 5: Rewrite `scripts/install.sh`

**Files:**
- Modify: `scripts/install.sh`

Curl-installable one-liner per spec section 7. POSIX bash, `set -euo pipefail`, no interactive prompts.

- [ ] **Step 1: Replace `scripts/install.sh` contents.**

  ```bash
  #!/usr/bin/env bash
  # Public one-line installer for loco-llm.
  # Usage:
  #   curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
  # Options:
  #   --dir <path>      override LOCO_LLM_HOME (default: $HOME/.loco-llm)
  #   --branch <name>   clone+checkout a branch instead of the latest tag
  #   --tag <vX.Y.Z>    pin to a specific tag
  set -euo pipefail

  REPO_URL="https://github.com/mtopcu1/loco-llm.git"
  REMOTE_HOST="github.com/mtopcu1/loco-llm"
  LOCO_LLM_HOME="${LOCO_LLM_HOME:-$HOME/.loco-llm}"
  PYTHON_MIN="3.11"
  REF_BRANCH=""
  REF_TAG=""

  die() { echo "error: $*" >&2; exit 1; }
  need() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)    LOCO_LLM_HOME="$2"; shift 2 ;;
      --branch) REF_BRANCH="$2"; shift 2 ;;
      --tag)    REF_TAG="$2"; shift 2 ;;
      *)        die "unknown argument: $1" ;;
    esac
  done

  need git
  need curl
  python3 - <<PY || die "python3 >= ${PYTHON_MIN} required"
  import sys
  major, minor = sys.version_info[:2]
  raise SystemExit(0 if (major, minor) >= (3, 11) else 1)
  PY

  if ! command -v uv >/dev/null 2>&1; then
    echo "==> installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi

  if [ -d "$LOCO_LLM_HOME/.git" ]; then
    actual_url="$(git -C "$LOCO_LLM_HOME" remote get-url origin 2>/dev/null || true)"
    case "$actual_url" in
      *"$REMOTE_HOST"*) ;;
      *) die "$LOCO_LLM_HOME exists but origin does not look like ${REMOTE_HOST}." ;;
    esac
    echo "==> updating existing checkout at $LOCO_LLM_HOME"
    git -C "$LOCO_LLM_HOME" fetch --tags --prune origin
  elif [ -e "$LOCO_LLM_HOME" ]; then
    die "$LOCO_LLM_HOME already exists and is not a git checkout; refusing to clobber."
  else
    echo "==> cloning to $LOCO_LLM_HOME"
    git clone "$REPO_URL" "$LOCO_LLM_HOME"
    git -C "$LOCO_LLM_HOME" fetch --tags --prune origin
  fi

  cd "$LOCO_LLM_HOME"

  if [ -n "$REF_BRANCH" ]; then
    target="$REF_BRANCH"
    echo "==> checking out branch $target"
  elif [ -n "$REF_TAG" ]; then
    target="$REF_TAG"
    echo "==> checking out tag $target"
  else
    target="$(git tag --list 'v*' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1 || true)"
    [ -n "$target" ] || die "no semver tags found on origin; pass --branch or --tag"
    echo "==> checking out latest tag $target"
  fi

  git checkout "$target"
  if [ -n "$REF_BRANCH" ]; then
    git pull --ff-only origin "$target"
  fi

  echo "==> creating venv at $LOCO_LLM_HOME/.venv"
  uv venv "$LOCO_LLM_HOME/.venv" --python "$PYTHON_MIN"

  echo "==> installing loco-llm (editable)"
  uv pip install --python "$LOCO_LLM_HOME/.venv/bin/python" -e "$LOCO_LLM_HOME"

  bin_dir="$HOME/.local/bin"
  mkdir -p "$bin_dir"
  ln -sf "$LOCO_LLM_HOME/.venv/bin/llm" "$bin_dir/llm"

  case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) echo "==> add this to your shell profile: export PATH=\"$bin_dir:\$PATH\"" ;;
  esac

  echo
  echo "loco-llm installed to $LOCO_LLM_HOME (ref: $target)"
  echo "next: run 'loco setup' to configure"
  ```

- [ ] **Step 2: Run shellcheck.**

  ```bash
  shellcheck scripts/install.sh
  ```

  Expected: no errors. If `shellcheck` is unavailable locally, skip; CI does not run it for now.

- [ ] **Step 3: Commit.**

  ```bash
  git add scripts/install.sh
  git commit -m "feat(install): curl-installable git-clone installer with uv editable install"
  ```

---

## Task 6: Rewrite `.github/workflows/ci.yml`

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/unit/test_workflows.py`

One job, PR-only, single Python version, uv-based.

- [ ] **Step 1: Update `tests/unit/test_workflows.py` `TestCIWorkflow` class.**

  Replace the class with:

  ```python
  class TestCIWorkflow:
      def test_triggers_on_pull_request_only(self):
          doc = _load("ci.yml")
          on = _get_on(doc)
          assert "pull_request" in on
          assert "push" not in on, "CI should not run on push to main"

      def test_skips_release_please_branches(self):
          doc = _load("ci.yml")
          job_if = doc["jobs"]["test"].get("if", "")
          assert "release-please--" in job_if

      def test_uses_uv_and_runs_pytest(self):
          doc = _load("ci.yml")
          steps = doc["jobs"]["test"]["steps"]
          uses = [s.get("uses", "") for s in steps]
          runs = [s.get("run", "") for s in steps]
          assert any(u.startswith("astral-sh/setup-uv@") for u in uses)
          assert any("pytest" in cmd for cmd in runs)
  ```

  Also delete `TestPublishWorkflow` entirely; publish.yml is being removed.

- [ ] **Step 2: Run workflow tests; expect failures.**

  ```bash
  python -m pytest tests/unit/test_workflows.py -q
  ```

- [ ] **Step 3: Replace `.github/workflows/ci.yml` with:**

  ```yaml
  name: ci
  on:
    pull_request:
      branches: [main]
  jobs:
    test:
      if: ${{ !startsWith(github.head_ref, 'release-please--') }}
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v3
        - name: Set up Python
          run: uv python install 3.11
        - name: Install
          run: |
            uv venv
            uv pip install -e ".[dev]"
        - name: Run pytest
          env:
            CI: "true"
            NO_COLOR: "1"
            TERM: "dumb"
          run: uv run pytest -q --tb=short
  ```

- [ ] **Step 4: Re-run workflow tests.**

  ```bash
  python -m pytest tests/unit/test_workflows.py::TestCIWorkflow -q
  ```

  Expected: all pass.

- [ ] **Step 5: Commit.**

  ```bash
  git add .github/workflows/ci.yml tests/unit/test_workflows.py
  git commit -m "ci: collapse to one PR-only test job using uv"
  ```

---

## Task 7: Strip `.github/workflows/release-please.yml` to tagging only

**Files:**
- Modify: `.github/workflows/release-please.yml`
- Modify: `tests/unit/test_workflows.py` (`TestReleasePleaseWorkflow`)

Drop the chained publish job, the release-pr-check job, all id-token permissions, all PyPI-related steps. Keep only the release-please action.

- [ ] **Step 1: Update `TestReleasePleaseWorkflow` in `tests/unit/test_workflows.py`.**

  Replace the class with:

  ```python
  class TestReleasePleaseWorkflow:
      def test_triggers_on_push_to_main(self):
          doc = _load("release-please.yml")
          on = _get_on(doc)
          assert "push" in on
          assert "main" in on["push"]["branches"]

      def test_supports_manual_dispatch(self):
          doc = _load("release-please.yml")
          on = _get_on(doc)
          assert "workflow_dispatch" in on

      def test_uses_release_please_action(self):
          doc = _load("release-please.yml")
          steps = doc["jobs"]["release-please"]["steps"]
          uses = [s.get("uses", "") for s in steps]
          assert any(u.startswith("googleapis/release-please-action@") for u in uses)

      def test_grants_only_minimum_permissions(self):
          doc = _load("release-please.yml")
          perms = doc.get("permissions", {})
          assert perms.get("contents") == "write"
          assert perms.get("pull-requests") == "write"
          assert "id-token" not in perms, "no OIDC needed without PyPI publish"

      def test_has_no_publish_or_check_jobs(self):
          doc = _load("release-please.yml")
          assert set(doc["jobs"].keys()) == {"release-please"}, (
              "release-please.yml should have exactly one job"
          )
  ```

- [ ] **Step 2: Run tests; expect failures.**

  ```bash
  python -m pytest tests/unit/test_workflows.py::TestReleasePleaseWorkflow -q
  ```

- [ ] **Step 3: Replace `.github/workflows/release-please.yml` with:**

  ```yaml
  name: release-please
  # Opens/updates the release PR on conventional commits. Merging the release
  # PR creates a git tag + GitHub Release. No publish job — there is nothing
  # to publish.
  on:
    push:
      branches: [main]
    workflow_dispatch:
  permissions:
    contents: write
    pull-requests: write
  jobs:
    release-please:
      runs-on: ubuntu-latest
      steps:
        - uses: googleapis/release-please-action@v4
          with:
            config-file: release-please-config.json
            manifest-file: .release-please-manifest.json
  ```

- [ ] **Step 4: Re-run tests.**

  ```bash
  python -m pytest tests/unit/test_workflows.py::TestReleasePleaseWorkflow -q
  ```

  Expected: all pass.

- [ ] **Step 5: Commit.**

  ```bash
  git add .github/workflows/release-please.yml tests/unit/test_workflows.py
  git commit -m "ci: strip release-please.yml to tagging only; drop publish job"
  ```

---

## Task 8: Delete remaining obsolete files

**Files:**
- Delete: `.github/workflows/publish.yml`
- Delete: `scripts/install-dev.sh`
- Delete: `scripts/migrate-from-v0.2.sh`
- Delete: `scripts/check_release_versions.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Delete the files.**

  ```bash
  git rm .github/workflows/publish.yml scripts/install-dev.sh scripts/migrate-from-v0.2.sh scripts/check_release_versions.py
  ```

- [ ] **Step 2: Drop `twine` from `pyproject.toml` `[project.optional-dependencies].dev`.**

  Open `pyproject.toml`, find the `dev = [...]` list under `[project.optional-dependencies]`, remove the `"twine>=5.0"` entry. Keep `"build>=1.0"` for local sanity (`uv build`); drop if you want to be even more minimal.

- [ ] **Step 3: Run the full test suite.**

  ```bash
  python -m pytest -q
  ```

  Expected: all green.

- [ ] **Step 4: Commit.**

  ```bash
  git add -A
  git commit -m "chore: remove publish.yml, install-dev/migrate scripts, twine dep"
  ```

---

## Task 9: Rewrite docs

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/RELEASE_SETUP.md`

### `README.md` — install / update section

- [ ] **Step 1: Replace the "Getting started" section with:**

  ```markdown
  ## Getting started (first time)

  Inside WSL2 (or any Linux/macOS shell with `git` and Python 3.11+):

  ```bash
  curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"   # if not already
  loco setup
  ```

  The installer clones the repo to `~/.loco-llm`, checks out the latest stable
  tag, creates a uv venv, and symlinks `loco`. Run `loco doctor` to verify.

  ### Updating

  ```bash
  loco update              # latest stable tag
  loco update --check      # report current vs. available, no changes
  loco update --branch X   # switch to a branch (hotfix testing)
  loco update --tag vX.Y.Z # pin to a specific tag (rollback)
  ```

  Bare `loco update` always re-anchors to the latest tag, even if you were on a
  branch.

  ### Upgrading from a prior pipx-based install

  If you previously installed with `pipx install loco-llm-cli`, switch over:

  ```bash
  pipx uninstall loco-llm-cli || true
  rm -f ~/.local/bin/llm
  curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
  ```
  ```

  Adjust phrasing to match the surrounding README voice; the substance above is the contract.

- [ ] **Step 2: Remove any other PyPI / pipx references throughout the README.**

  ```bash
  rg -n "pypi|pipx" README.md
  ```

  Update or delete each hit.

### `CONTRIBUTING.md`

- [ ] **Step 3: Remove the PyPI publishing section.**

  Open `CONTRIBUTING.md`, delete anything mentioning PyPI, `pipx install`, `twine`, or the publish flow. Keep the Conventional Commits section (it's the gate for release-please). Add a short "Dev install" section:

  ```markdown
  ## Dev install

  ```bash
  git clone https://github.com/mtopcu1/loco-llm.git
  cd loco-llm
  uv venv && uv pip install -e ".[dev]"
  uv run pytest
  ```

  No separate `install-dev.sh`. To use this checkout as your runtime install,
  set `LOCO_LLM_HOME=$(pwd)` or configure `repo_root` in `loco settings`.
  ```

### `docs/RELEASE_SETUP.md`

- [ ] **Step 4: Replace `docs/RELEASE_SETUP.md` with a slim version:**

  ```markdown
  # Release automation setup (one-time)

  ## 1. Enable Actions to open PRs

  GitHub → Settings → Actions → General → Workflow permissions:
  - Read and write permissions
  - Allow GitHub Actions to create and approve pull requests

  Without these, release-please can prepare a release branch but cannot open the PR.

  ## 2. Branch protection on `main`

  Require one status check: `test`. Allow admin bypass — release PRs are opened
  by `github-actions[bot]` and don't get checks attached (a GitHub limitation,
  not a workflow bug). The release PR only edits version + CHANGELOG; review
  the diff and admin-merge.

  ## 3. There is no PyPI

  Distribution is by git tag. Merging the release PR creates the tag and a
  GitHub Release with the CHANGELOG. `loco update` consumes the tag. No PyPI
  trusted publisher to configure, no wheel to upload, no scaffold tarball.

  ## 4. Flow

  ```mermaid
  flowchart LR
    pr[Feature PR] --> ci[ci.yml tests] --> merge
    merge --> rp[release-please.yml]
    rp --> relpr[Release PR opened/updated]
    relpr --> mergerel[Merge release PR, admin OK]
    mergerel --> tag[Tag vX.Y.Z + GitHub Release]
    tag --> users[users: loco update]
  ```
  ```

- [ ] **Step 5: Commit.**

  ```bash
  git add README.md CONTRIBUTING.md docs/RELEASE_SETUP.md
  git commit -m "docs: rewrite install/update/release docs for git-tag distribution"
  ```

---

## Task 10: Final verification

- [ ] **Step 1: Full pytest run.**

  ```bash
  python -m pytest -q
  ```

  Expected: all green.

- [ ] **Step 2: Validate workflow YAML parses (sanity beyond tests).**

  ```bash
  python -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]"
  ```

  Expected: no exception. Only `ci.yml` and `release-please.yml` should exist in that directory.

- [ ] **Step 3: shellcheck install.sh if available.**

  ```bash
  shellcheck scripts/install.sh
  ```

- [ ] **Step 4: Smoke-check `loco --version` from this checkout.**

  ```bash
  uv run loco --version
  ```

  Expected: `loco 0.3.2 (branch: feat/git-tag-distribution)` (or similar suffix since you're on a branch).

- [ ] **Step 5: Push the branch.**

  ```bash
  git push -u origin feat/git-tag-distribution
  ```

- [ ] **Step 6: Open the PR.**

  Title: `feat!: replace PyPI distribution with git-tag pull model`

  Body (paste verbatim):

  ```
  Implements docs/superpowers/specs/2026-05-19-git-tag-distribution-design.md.

  Distribution is now git-tag based (hermes-agent pattern):
  - curl install.sh clones to ~/.loco-llm and editable-installs via uv
  - loco update fetches tags and re-anchors to the latest stable tag
  - --branch / --tag / --check flags for hotfixes, pinning, dry-runs
  - loco doctor + loco --version warn when HEAD is off-tag

  CI collapsed:
  - ci.yml: one job, PR-only, single Python, uv
  - release-please.yml: tagging only, no publish job, no PyPI

  Deleted: publish.yml, scaffold tarball machinery, PyPI version check,
  install-dev.sh, migrate-from-v0.2.sh, check_release_versions.py.

  BREAKING CHANGE: existing pipx-installed users must uninstall and re-run
  the curl installer. See README "Upgrading" section.
  ```

---

## Task 11: Post-merge actions (manual)

Not executable in the PR — do these after the PR merges and release-please cuts the next tag.

- [ ] **Step 1: Re-point branch protection.**

  ```bash
  gh api --method PUT repos/mtopcu1/loco-llm/branches/main/protection --input - <<'JSON'
  {
    "required_status_checks": { "strict": true, "contexts": ["test"] },
    "enforce_admins": false,
    "required_pull_request_reviews": null,
    "restrictions": null,
    "required_linear_history": false,
    "allow_force_pushes": false,
    "allow_deletions": false
  }
  JSON
  ```

- [ ] **Step 2: Remove the PyPI trusted publisher entries.**

  Go to https://pypi.org/manage/account/publishing/ and delete any pending or active publishers pointing at `mtopcu1/loco-llm` or `mtopcu1/local-llm-scaffold`. Optional: yank the `loco-llm-cli` / `locallm-cli` reservations or push a `0.0.0` deprecation placeholder.

- [ ] **Step 3: Merge the release-please PR that this rewrite triggers.**

  The breaking-change commit will bump pre-1.0 minor (so `0.4.0`). After merging the release PR, verify the tag and GitHub Release exist:

  ```bash
  gh release view v0.4.0 --repo mtopcu1/loco-llm
  ```

- [ ] **Step 4: Smoke test in a fresh environment.**

  In WSL2:

  ```bash
  rm -rf ~/.loco-llm ~/.local/bin/llm   # if any leftover
  curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
  ~/.local/bin/loco --version            # should print: llm 0.4.0
  ~/.local/bin/loco update --check       # should print: Already on latest stable.
  ```

- [ ] **Step 5: Smoke test the hotfix path.**

  ```bash
  git -C ~/.loco-llm fetch origin
  loco update --branch main              # if main is ahead of v0.4.0
  loco update                            # re-anchors to v0.4.0
  ```

- [ ] **Step 6: Cut a no-op v0.4.1 to verify the update path.**

  Land a trivial `fix:` commit (e.g. typo in README), merge the release-please PR, then on the test machine:

  ```bash
  loco update
  # expected: "updated to v0.4.1."
  ```

---

## Out of scope (deliberately not in this plan)

- Renaming `~/.config/localllm/` / `~/.local/share/localllm/` to `loco-llm`.
- PowerShell native-Windows installer.
- `--prerelease` channel support.
- Compile-to-binary distribution.
- Automatic post-update verification beyond `loco --version`.
