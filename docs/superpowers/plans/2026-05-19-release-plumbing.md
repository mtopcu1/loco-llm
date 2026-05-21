# LocalLLM Release Plumbing Implementation Plan (Cut 1 — v0.2.1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add release-please-driven versioning, CI, and PyPI / GitHub-Release publishing to LocalLLM, then smoke-test the pipeline by cutting `v0.2.1` (a no-behavior-change patch release).

**Architecture:** Install `release-please` as a GitHub Action that maintains a long-lived release PR, driven by Conventional Commits on `main`. A second workflow runs on `release: published` and uploads a wheel + sdist to PyPI via OIDC trusted publishing, plus a `scaffold-<tag>.tar.gz` + `.sha256` sidecar to the GitHub Release for the future `loco update` command (Plan B) to consume. A standard pytest-based CI workflow runs on every PR.

**Tech Stack:** Python 3.11+, Hatchling build backend, PyPI (Warehouse) OIDC, GitHub Actions (`release-please-action@v4`, `actions/setup-python@v5`, `pypa/gh-action-pypi-publish@release/v1`, `softprops/action-gh-release@v2`), Conventional Commits.

**Related spec:** `docs/superpowers/specs/2026-05-19-update-distribution-and-versioning-design.md` — sections §10 (versioning automation) and §13 step 1 (release sequencing) are the relevant parts. Plan B (layered model + `loco update` + migration) is deferred until Plan A's smoke release succeeds.

---

## Background — what exists today (for the engineer with zero context)

- LocalLLM is a Python Typer CLI (`localllm-cli` package, `loco` binary) installed today via a clone-and-bash flow. Version is hand-edited in `pyproject.toml` and `src/llm_cli/__init__.py`, both currently `"0.2.0"`. No git tags. No CI. No PyPI presence.
- Repo: `github.com/mtopcu1/local-llm-scaffold`, default branch `main`. PowerShell on the maintainer's Windows host; WSL2 for runtime testing. CI will run on `ubuntu-latest` (Linux), which is fine — the unit tests are Linux/Windows-portable, and the WSL/PTY tests are guarded by the `tui` pytest marker and `sys_platform != 'win32'` (they skip on `ubuntu-latest` cleanly).
- Build backend is Hatchling (declared in `pyproject.toml`). `python -m build` should produce both `localllm_cli-X.Y.Z-py3-none-any.whl` and `localllm_cli-X.Y.Z.tar.gz` without extra config.
- This plan adds **no** CLI behavior. Everything here is project tooling. Plan B adds the actual `loco update` command.

## File map

**Create:**
- `release-please-config.json` (repo root) — release-please package config.
- `.release-please-manifest.json` (repo root) — release-please state file.
- `.github/workflows/release-please.yml` — opens/updates the release PR.
- `.github/workflows/ci.yml` — pytest + build check on PRs.
- `.github/workflows/publish.yml` — fires on `release: published`, uploads to PyPI + attaches scaffold tarball.
- `CONTRIBUTING.md` (repo root) — Conventional Commits cheat sheet. Dev install path is added later in Plan B.
- `tests/unit/test_release_config.py` — validates `release-please-config.json` and the manifest parse + have expected shape.
- `tests/unit/test_workflows.py` — validates the three YAML workflows parse + carry required keys (OIDC permission, tarball step, etc.).

**Modify:**
- `src/llm_cli/__init__.py` — add `# x-release-please-version` marker comment on the `__version__` line.
- `pyproject.toml` — add PyPI-friendly metadata (`license`, `authors`, `urls`, `classifiers`, `readme`) if missing; verify `python -m build` produces a clean wheel.

**Untouched:**
- `install.sh`, `src/llm_cli/main.py`, all `commands/`, all `core/`, all `tests/integration/`, all `runtimes/`, all `configs/`, all `docs/` other than the new spec and CONTRIBUTING.md.

---

## Manual prerequisites (do these once, before Task 1)

These cannot be automated. Allocate ~15 minutes.

- [ ] **MP1: Confirm PyPI name availability.**

  Run from any shell with network access:

  ```bash
  curl -sI https://pypi.org/pypi/localllm-cli/json | head -n 1
  ```

  Expected: `HTTP/2 404` (confirmed by spec-writing on 2026-05-19; name was available). If this returns `200`, stop and discuss a renamed package — the spec assumes `localllm-cli`.

- [ ] **MP2: Create a PyPI account (if not already present).**

  Sign up at https://pypi.org/account/register/. Enable 2FA. This is the account that will own `localllm-cli`.

- [ ] **MP3: Reserve the name with an initial manual upload.**

  We deliberately make a one-shot manual `twine upload` of a placeholder `0.0.0` build to reserve the name before automation takes over. This is the cleanest way to bootstrap OIDC trusted publishing (PyPI requires the project to exist before you can configure trusted publishing).

  Run locally from the repo root in WSL or Linux:

  ```bash
  python3 -m venv /tmp/release-bootstrap
  /tmp/release-bootstrap/bin/pip install build twine
  # Temporarily set version to 0.0.0
  cp pyproject.toml pyproject.toml.bak
  sed -i 's/^version = "0.2.0"$/version = "0.0.0"/' pyproject.toml
  /tmp/release-bootstrap/bin/python -m build
  /tmp/release-bootstrap/bin/twine upload dist/*0.0.0*
  # Restore
  mv pyproject.toml.bak pyproject.toml
  rm -rf dist/ build/ *.egg-info
  ```

  Use a temporary API token from https://pypi.org/manage/account/token/ scoped to "Entire account" for this one upload. Revoke it immediately after — from now on, automation uses OIDC.

- [ ] **MP4: Configure PyPI trusted publishing for the project.**

  Go to https://pypi.org/manage/project/localllm-cli/settings/publishing/ and add a "trusted publisher" entry with:
  - PyPI Project Name: `localllm-cli`
  - Owner: `mtopcu1`
  - Repository name: `local-llm-scaffold`
  - Workflow name: `publish.yml`
  - Environment name: leave blank (we are not using GH Environments yet)

  This authorizes the publish workflow to upload future versions without a long-lived token.

- [ ] **MP5: Verify GitHub repo settings.**

  At https://github.com/mtopcu1/local-llm-scaffold/settings/actions:
  - "Allow GitHub Actions to create and approve pull requests" → **enabled** (release-please needs this to open the release PR).
  - Default permissions: "Read and write permissions" for `GITHUB_TOKEN` — required for release-please to push tags and create releases.

---

## Task 1: Add PyPI-friendly metadata to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml` (the `[project]` table)
- Verify: `python -m build` produces a clean wheel + sdist

**Why:** PyPI rejects uploads whose metadata is too sparse (no description, no license, no URLs). Today's `pyproject.toml` is minimal. Get it production-grade before automation tries to upload it.

- [ ] **Step 1: Read the current `pyproject.toml` to confirm the starting state.**

  Run: `cat pyproject.toml`

  Expected to match the snippet:

  ```toml
  [project]
  name = "localllm-cli"
  version = "0.2.0"
  description = "Personal control plane for local LLM runtimes"
  requires-python = ">=3.11"
  dependencies = [ ... ]
  ```

  (If `[project]` already has `license`, `readme`, `authors`, `urls`, `classifiers` filled in, skip ahead to Step 3 and just verify the build.)

- [ ] **Step 2: Replace the `[project]` table with the production-grade version.**

  In `pyproject.toml`, replace the existing `[project]` table with:

  ```toml
  [project]
  name = "localllm-cli"
  version = "0.2.0"
  description = "Personal control plane for local LLM runtimes."
  readme = "README.md"
  requires-python = ">=3.11"
  license = { text = "MIT" }
  authors = [
      { name = "Melih Topcu" },
  ]
  keywords = ["llm", "wsl", "vllm", "llama.cpp", "local"]
  classifiers = [
      "Development Status :: 3 - Alpha",
      "Environment :: Console",
      "Intended Audience :: Developers",
      "License :: OSI Approved :: MIT License",
      "Operating System :: POSIX :: Linux",
      "Programming Language :: Python :: 3",
      "Programming Language :: Python :: 3.11",
      "Programming Language :: Python :: 3.12",
      "Topic :: Scientific/Engineering :: Artificial Intelligence",
      "Topic :: System :: Systems Administration",
  ]
  dependencies = [
      "typer>=0.12,<1.0",
      "pyyaml>=6.0",
      "httpx>=0.27",
      "rich>=13.7",
      "questionary>=2.0,<3",
  ]

  [project.urls]
  Homepage = "https://github.com/mtopcu1/local-llm-scaffold"
  Repository = "https://github.com/mtopcu1/local-llm-scaffold"
  Issues = "https://github.com/mtopcu1/local-llm-scaffold/issues"

  [project.optional-dependencies]
  dev = [
      "pytest>=8.0",
      "pytest-mock>=3.12",
      "pexpect>=4.9; sys_platform != 'win32'",
      "build>=1.0",
      "twine>=5.0",
  ]

  [project.scripts]
  llm = "llm_cli.main:app"
  ```

  Note the additions: `readme = "README.md"`, `license = { text = "MIT" }`, `authors`, `keywords`, `classifiers`, `[project.urls]`, and `build`+`twine` in the dev extras. Everything else is unchanged from the current file.

  If LocalLLM is not actually MIT-licensed today, replace the `license` field with the correct SPDX expression (e.g. `{ text = "Apache-2.0" }`) and update the classifier accordingly. If unsure, leave it as MIT — that's the most common default for personal-tooling-grown-up projects.

- [ ] **Step 3: Add a LICENSE file if none exists.**

  Run: `ls LICENSE LICENSE.md LICENSE.txt 2>/dev/null`

  If empty (no license file), create one. From the repo root, run:

  ```bash
  cat > LICENSE <<'EOF'
  MIT License

  Copyright (c) 2026 Melih Topcu

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
  EOF
  ```

  If a LICENSE file already exists, skip this step.

- [ ] **Step 4: Build the wheel and sdist locally.**

  In WSL (or any Linux/macOS shell):

  ```bash
  python3 -m venv /tmp/build-check
  /tmp/build-check/bin/pip install --upgrade build twine
  rm -rf dist/ build/ *.egg-info
  /tmp/build-check/bin/python -m build
  ls dist/
  ```

  Expected output in `dist/`:

  ```
  localllm_cli-0.2.0-py3-none-any.whl
  localllm_cli-0.2.0.tar.gz
  ```

  If `python -m build` fails, read the error — the most common cause is a missing `README.md` (referenced in step 2's `readme = ...`). Fix and re-run.

- [ ] **Step 5: Verify the wheel passes `twine check`.**

  ```bash
  /tmp/build-check/bin/twine check dist/*
  ```

  Expected:

  ```
  Checking dist/localllm_cli-0.2.0-py3-none-any.whl: PASSED
  Checking dist/localllm_cli-0.2.0.tar.gz: PASSED
  ```

  If any check returns `FAILED`, twine prints the reason (usually a malformed `long_description` or missing classifier). Fix and re-run from Step 4.

- [ ] **Step 6: Clean up build artifacts.**

  ```bash
  rm -rf dist/ build/ *.egg-info /tmp/build-check
  ```

- [ ] **Step 7: Commit.**

  ```bash
  git add pyproject.toml LICENSE
  git commit -m "chore(pyproject): add PyPI metadata and LICENSE for distribution"
  ```

  Note the `chore:` prefix — this commit is intentionally **not** included in the CHANGELOG. The version stays `0.2.0` until release-please decides otherwise.

---

## Task 2: Add the `x-release-please-version` marker to `src/llm_cli/__init__.py`

**Files:**
- Modify: `src/llm_cli/__init__.py`

**Why:** release-please's `python` release type automatically bumps `pyproject.toml`'s `version` line, but our `__version__` line in `__init__.py` is in a separate file. release-please updates "extra files" only when it finds a magic marker comment on the line to be replaced.

- [ ] **Step 1: Read the current `src/llm_cli/__init__.py`.**

  Run: `cat src/llm_cli/__init__.py`

  Expected single line:

  ```python
  __version__ = "0.2.0"
  ```

- [ ] **Step 2: Add the marker comment.**

  Replace the file contents with:

  ```python
  __version__ = "0.2.0"  # x-release-please-version
  ```

  (Same line, marker appended as an inline comment.)

- [ ] **Step 3: Verify Python still imports the module.**

  ```bash
  python3 -c "from llm_cli import __version__; print(__version__)"
  ```

  Expected output: `0.2.0`

  (Run from the repo root with the existing editable venv activated, or any environment that has `llm_cli` importable.)

- [ ] **Step 4: Verify pytest still passes.**

  ```bash
  pytest tests/unit -q
  ```

  Expected: all unit tests pass. The marker comment is just a comment — nothing observable changes.

- [ ] **Step 5: Commit.**

  ```bash
  git add src/llm_cli/__init__.py
  git commit -m "chore(release): add x-release-please-version marker to __init__.py"
  ```

---

## Task 3: Create `release-please-config.json` (test-first)

**Files:**
- Create: `tests/unit/test_release_config.py`
- Create: `release-please-config.json`

**Why:** release-please's behavior is driven entirely by this file. A typo here means broken releases. We test it the way we test any parsed config: load it, assert on shape.

- [ ] **Step 1: Write the failing test.**

  Create `tests/unit/test_release_config.py`:

  ```python
  """Validate the release-please configuration files.

  These are not Python files but JSON / structured data we own; if they
  break, releases break. Catch typos in CI rather than on the next release.
  """
  from __future__ import annotations

  import json
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parents[2]


  def _load(name: str) -> dict:
      path = REPO_ROOT / name
      assert path.is_file(), f"missing {name} at repo root"
      return json.loads(path.read_text(encoding="utf-8"))


  def test_release_please_config_is_python_release_type():
      cfg = _load("release-please-config.json")
      assert cfg["release-type"] == "python"


  def test_release_please_config_declares_root_package():
      cfg = _load("release-please-config.json")
      assert "." in cfg["packages"], "expected the root package keyed by '.'"
      root = cfg["packages"]["."]
      assert root["package-name"] == "localllm-cli"


  def test_release_please_config_updates_init_py():
      cfg = _load("release-please-config.json")
      extras = cfg["packages"]["."].get("extra-files", [])
      paths = {entry["path"] for entry in extras if isinstance(entry, dict)}
      assert "src/llm_cli/__init__.py" in paths, (
          "release-please must be configured to update __version__ in "
          "src/llm_cli/__init__.py"
      )


  def test_release_please_changelog_sections_cover_feat_and_fix():
      cfg = _load("release-please-config.json")
      sections = cfg.get("changelog-sections", [])
      types = {s["type"] for s in sections}
      assert "feat" in types
      assert "fix" in types


  def test_release_please_manifest_starts_at_known_version():
      manifest = _load(".release-please-manifest.json")
      assert manifest["."] in {"0.2.0", "0.2.1"}, (
          "the manifest's recorded version for '.' should match the last "
          "released version; if you're bumping pre-release, update this test"
      )
  ```

- [ ] **Step 2: Run the test to verify it fails.**

  ```bash
  pytest tests/unit/test_release_config.py -v
  ```

  Expected: all five tests FAIL with `AssertionError: missing release-please-config.json at repo root` (or similar). This proves the test is wired correctly.

- [ ] **Step 3: Create `release-please-config.json` at the repo root.**

  ```json
  {
    "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
    "release-type": "python",
    "include-component-in-tag": false,
    "include-v-in-tag": true,
    "packages": {
      ".": {
        "package-name": "localllm-cli",
        "release-type": "python",
        "extra-files": [
          {
            "type": "generic",
            "path": "src/llm_cli/__init__.py"
          }
        ]
      }
    },
    "changelog-sections": [
      { "type": "feat",     "section": "Features" },
      { "type": "fix",      "section": "Bug Fixes" },
      { "type": "perf",     "section": "Performance" },
      { "type": "docs",     "section": "Documentation" },
      { "type": "refactor", "section": "Refactor", "hidden": true },
      { "type": "test",     "section": "Tests", "hidden": true },
      { "type": "chore",    "section": "Chores", "hidden": true },
      { "type": "ci",       "section": "CI", "hidden": true },
      { "type": "style",    "section": "Style", "hidden": true }
    ]
  }
  ```

  Notes:
  - `include-v-in-tag: true` makes tags `v0.4.1` (matches the spec).
  - `include-component-in-tag: false` because we have a single package.
  - The duplicate `release-type` inside the package entry is defensive — release-please ignores the outer one in some versions of the schema.
  - All non-changelog types are still declared with `hidden: true` so they parse cleanly without appearing in `CHANGELOG.md`.

- [ ] **Step 4: Create `.release-please-manifest.json` at the repo root.**

  ```json
  {
    ".": "0.2.0"
  }
  ```

  This tells release-please that the last released version of the root package was 0.2.0. The next merged release PR will bump to 0.2.1 / 0.3.0 / etc. depending on commits.

- [ ] **Step 5: Run the tests to verify they pass.**

  ```bash
  pytest tests/unit/test_release_config.py -v
  ```

  Expected: all five tests PASS.

- [ ] **Step 6: Commit.**

  ```bash
  git add tests/unit/test_release_config.py release-please-config.json .release-please-manifest.json
  git commit -m "ci: add release-please config and manifest"
  ```

---

## Task 4: Create `.github/workflows/release-please.yml` (test-first)

**Files:**
- Create: `tests/unit/test_workflows.py`
- Create: `.github/workflows/release-please.yml`

**Why:** This is the workflow that opens the release PR. Wrong trigger or missing permissions = no PRs ever appear, and you discover this weeks later. Validate structure.

- [ ] **Step 1: Write the failing test.**

  Create `tests/unit/test_workflows.py`:

  ```python
  """Validate the GitHub Actions workflows for structural correctness.

  This does NOT execute the workflows — it just parses the YAML and
  asserts the required triggers, permissions, and steps are present.
  Catches misconfigurations (e.g. missing OIDC permission) in unit-test
  time rather than on the next release.
  """
  from __future__ import annotations

  from pathlib import Path
  from typing import Any

  import pytest
  import yaml

  WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


  def _load(name: str) -> dict[str, Any]:
      path = WORKFLOWS_DIR / name
      assert path.is_file(), f"missing workflow {name}"
      # PyYAML treats the unquoted `on:` key as boolean True; load and accept
      # either key form.
      doc = yaml.safe_load(path.read_text(encoding="utf-8"))
      return doc


  def _get_on(doc: dict[str, Any]) -> dict[str, Any]:
      # GitHub YAML uses `on:` which PyYAML may parse as the Python bool True.
      if True in doc:
          return doc[True]
      return doc["on"]


  class TestReleasePleaseWorkflow:
      def test_triggers_on_push_to_main(self):
          doc = _load("release-please.yml")
          on = _get_on(doc)
          assert "push" in on
          assert "main" in on["push"]["branches"]

      def test_uses_release_please_action(self):
          doc = _load("release-please.yml")
          jobs = doc["jobs"]
          steps = next(iter(jobs.values()))["steps"]
          uses = [s.get("uses", "") for s in steps]
          assert any(u.startswith("googleapis/release-please-action@") for u in uses)
  ```

  (We'll add classes for `ci.yml` and `publish.yml` in their own tasks.)

- [ ] **Step 2: Run the test to verify it fails.**

  ```bash
  pytest tests/unit/test_workflows.py -v
  ```

  Expected: both tests in `TestReleasePleaseWorkflow` FAIL with `missing workflow release-please.yml`.

- [ ] **Step 3: Create `.github/workflows/release-please.yml`.**

  ```yaml
  name: release-please

  on:
    push:
      branches: [main]

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

  Notes:
  - `contents: write` lets release-please push the version-bump commit on its release PR branch.
  - `pull-requests: write` lets it open / update the release PR.
  - We do **not** need `id-token: write` here (that's only for the publish workflow).

- [ ] **Step 4: Run the tests to verify they pass.**

  ```bash
  pytest tests/unit/test_workflows.py::TestReleasePleaseWorkflow -v
  ```

  Expected: both tests PASS.

- [ ] **Step 5: Commit.**

  ```bash
  git add tests/unit/test_workflows.py .github/workflows/release-please.yml
  git commit -m "ci: add release-please workflow for automated release PRs"
  ```

---

## Task 5: Create `.github/workflows/ci.yml` (test-first)

**Files:**
- Modify: `tests/unit/test_workflows.py` (add `TestCIWorkflow` class)
- Create: `.github/workflows/ci.yml`

**Why:** Run pytest + build check on every PR. Without this, regressions land on `main` and only show up at release time.

- [ ] **Step 1: Add the failing tests.**

  Append to `tests/unit/test_workflows.py`:

  ```python
  class TestCIWorkflow:
      def test_triggers_on_pr_and_push_to_main(self):
          doc = _load("ci.yml")
          on = _get_on(doc)
          assert "pull_request" in on
          assert "push" in on
          assert "main" in on["push"]["branches"]

      def test_runs_pytest_on_supported_python_versions(self):
          doc = _load("ci.yml")
          test_job = doc["jobs"].get("test")
          assert test_job is not None, "expected a 'test' job"
          matrix = test_job.get("strategy", {}).get("matrix", {})
          versions = {str(v) for v in matrix.get("python-version", [])}
          assert {"3.11", "3.12"}.issubset(versions), (
              f"expected pytest matrix on 3.11 and 3.12, got {versions}"
          )
          run_steps = [s.get("run", "") for s in test_job["steps"] if "run" in s]
          assert any("pytest" in cmd for cmd in run_steps), (
              "expected at least one step that runs pytest"
          )

      def test_has_build_check_job(self):
          doc = _load("ci.yml")
          build_job = doc["jobs"].get("build-check")
          assert build_job is not None, "expected a 'build-check' job"
          run_steps = [s.get("run", "") for s in build_job["steps"] if "run" in s]
          assert any("python -m build" in cmd for cmd in run_steps)
          assert any("twine check" in cmd for cmd in run_steps)
  ```

- [ ] **Step 2: Run the new tests to verify they fail.**

  ```bash
  pytest tests/unit/test_workflows.py::TestCIWorkflow -v
  ```

  Expected: all three tests FAIL with `missing workflow ci.yml`.

- [ ] **Step 3: Create `.github/workflows/ci.yml`.**

  ```yaml
  name: ci

  on:
    pull_request:
    push:
      branches: [main]

  jobs:
    test:
      runs-on: ubuntu-latest
      strategy:
        fail-fast: false
        matrix:
          python-version: ["3.11", "3.12"]
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: ${{ matrix.python-version }}
            cache: pip
        - name: Install
          run: |
            python -m pip install --upgrade pip
            pip install -e '.[dev]'
        - name: Run pytest
          run: pytest -q

    build-check:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"
        - name: Install build + twine
          run: |
            python -m pip install --upgrade pip
            pip install build twine
        - name: Build wheel and sdist
          run: python -m build
        - name: twine check
          run: twine check dist/*
  ```

  Notes:
  - We deliberately do **not** invoke `loco doctor` or `loco specs --check` in CI — they assume runtime hardware that `ubuntu-latest` doesn't have. Plan B will revisit if we want a docs-regen check (`loco doctor render-requirements && git diff --exit-code`).
  - The `tui` pytest marker is automatically skipped on Linux (the `pexpect>=4.9; sys_platform != 'win32'` extra is *installed*, but most `tui` tests `pytest.skip` themselves outside WSL — verify this assumption in Step 4).

- [ ] **Step 4: Verify locally that the test commands actually work.**

  Simulate the CI environment locally:

  ```bash
  python3 -m venv /tmp/ci-check
  /tmp/ci-check/bin/pip install -e '.[dev]'
  /tmp/ci-check/bin/pytest -q
  ```

  Expected: all unit and non-TUI integration tests pass. TUI tests should report as `skipped` (because we're not in WSL with a real PTY), not `failed`. If they `fail` instead of `skip`, open a follow-up issue and either fix the skip condition or temporarily mark them with `@pytest.mark.skipif(...)` — do not paper over real test failures.

  Clean up: `rm -rf /tmp/ci-check`

- [ ] **Step 5: Run the workflow tests to verify they pass.**

  ```bash
  pytest tests/unit/test_workflows.py::TestCIWorkflow -v
  ```

  Expected: all three tests PASS.

- [ ] **Step 6: Commit.**

  ```bash
  git add tests/unit/test_workflows.py .github/workflows/ci.yml
  git commit -m "ci: add pytest + build-check workflow for PRs"
  ```

---

## Task 6: Create `.github/workflows/publish.yml` with scaffold tarball attach (test-first)

**Files:**
- Modify: `tests/unit/test_workflows.py` (add `TestPublishWorkflow` class)
- Create: `.github/workflows/publish.yml`

**Why:** This is the workflow that ships releases. Per the spec §10.5, it must (a) publish to PyPI via OIDC (so we need `id-token: write`), (b) build the scaffold tarball with a sha256 sidecar, and (c) attach all artifacts to the GitHub Release. Each of those is one assertion.

- [ ] **Step 1: Add the failing tests.**

  Append to `tests/unit/test_workflows.py`:

  ```python
  class TestPublishWorkflow:
      def test_triggers_on_release_published(self):
          doc = _load("publish.yml")
          on = _get_on(doc)
          assert "release" in on
          types = on["release"].get("types", [])
          assert "published" in types

      def test_has_id_token_write_permission_for_oidc(self):
          doc = _load("publish.yml")
          # Either job-level or workflow-level permissions are acceptable;
          # we accept the first one that grants id-token: write.
          def _has(d: dict[str, Any]) -> bool:
              perms = d.get("permissions", {})
              return perms.get("id-token") == "write"

          if _has(doc):
              return
          for job in doc["jobs"].values():
              if _has(job):
                  return
          pytest.fail(
              "expected id-token: write at workflow or job level for PyPI OIDC"
          )

      def test_uses_pypi_publish_action(self):
          doc = _load("publish.yml")
          all_steps = []
          for job in doc["jobs"].values():
              all_steps.extend(job.get("steps", []))
          uses = [s.get("uses", "") for s in all_steps]
          assert any(
              u.startswith("pypa/gh-action-pypi-publish@") for u in uses
          ), "expected pypa/gh-action-pypi-publish step"

      def test_builds_scaffold_tarball_and_sha256(self):
          doc = _load("publish.yml")
          all_steps = []
          for job in doc["jobs"].values():
              all_steps.extend(job.get("steps", []))
          run_blobs = "\n".join(s.get("run", "") for s in all_steps)
          assert "tar czf" in run_blobs, "expected a tar czf step"
          assert "scaffold-" in run_blobs, (
              "expected scaffold-<tag>.tar.gz naming pattern"
          )
          assert "sha256sum" in run_blobs, (
              "expected sha256sum to produce the .sha256 sidecar"
          )

      def test_attaches_assets_to_github_release(self):
          doc = _load("publish.yml")
          all_steps = []
          for job in doc["jobs"].values():
              all_steps.extend(job.get("steps", []))
          uses = [s.get("uses", "") for s in all_steps]
          run_blobs = "\n".join(s.get("run", "") for s in all_steps)
          attaches_via_action = any(
              u.startswith("softprops/action-gh-release@") for u in uses
          )
          attaches_via_gh_cli = "gh release upload" in run_blobs
          assert attaches_via_action or attaches_via_gh_cli, (
              "expected either softprops/action-gh-release or `gh release upload` "
              "to attach the scaffold tarball to the GitHub Release"
          )
  ```

- [ ] **Step 2: Run the new tests to verify they fail.**

  ```bash
  pytest tests/unit/test_workflows.py::TestPublishWorkflow -v
  ```

  Expected: all five tests FAIL with `missing workflow publish.yml`.

- [ ] **Step 3: Create `.github/workflows/publish.yml`.**

  ```yaml
  name: publish

  on:
    release:
      types: [published]

  permissions:
    contents: write   # to upload release assets
    id-token: write   # for PyPI OIDC trusted publishing

  jobs:
    publish:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
          with:
            ref: ${{ github.event.release.tag_name }}

        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"

        - name: Install build tooling
          run: |
            python -m pip install --upgrade pip
            pip install build

        - name: Build wheel and sdist
          run: python -m build

        - name: Publish to PyPI via OIDC
          uses: pypa/gh-action-pypi-publish@release/v1
          with:
            packages-dir: dist/

        - name: Build scaffold tarball
          env:
            TAG: ${{ github.event.release.tag_name }}
          run: |
            tar czf "scaffold-${TAG}.tar.gz" \
              runtimes configs benchmarks requirements.yaml
            sha256sum "scaffold-${TAG}.tar.gz" > "scaffold-${TAG}.tar.gz.sha256"

        - name: Attach assets to GitHub Release
          env:
            GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
            TAG: ${{ github.event.release.tag_name }}
          run: |
            gh release upload "${TAG}" \
              dist/*.whl \
              dist/*.tar.gz \
              "scaffold-${TAG}.tar.gz" \
              "scaffold-${TAG}.tar.gz.sha256" \
              --clobber
  ```

  Notes:
  - `actions/checkout@v4` with `ref: ${{ github.event.release.tag_name }}` ensures we build from the tag, not from whatever `main` is at the time the workflow runs.
  - `id-token: write` enables PyPI OIDC. With MP4 done (the trusted publisher config), no API token is needed.
  - The `gh release upload --clobber` step attaches all four artifacts (wheel, sdist, scaffold tarball, sha256). `--clobber` lets re-runs work idempotently.
  - The `dist/*.tar.gz` glob picks up the Python sdist; the explicitly-named `scaffold-${TAG}.tar.gz` is uploaded separately because it lives in the repo root, not in `dist/`.

- [ ] **Step 4: Sanity-check the tarball command locally.**

  In WSL (or any Linux shell), from the repo root, run the tarball steps by hand:

  ```bash
  TAG=v0.2.1-local-test
  tar czf "scaffold-${TAG}.tar.gz" runtimes configs benchmarks requirements.yaml
  sha256sum "scaffold-${TAG}.tar.gz" > "scaffold-${TAG}.tar.gz.sha256"
  ls -la "scaffold-${TAG}.tar.gz" "scaffold-${TAG}.tar.gz.sha256"
  tar tzf "scaffold-${TAG}.tar.gz" | head -n 20
  ```

  Expected: tarball is created, contains `runtimes/`, `configs/`, `benchmarks/`, `requirements.yaml` paths. SHA256 file contains a single line like `<hash>  scaffold-v0.2.1-local-test.tar.gz`.

  Clean up: `rm scaffold-v0.2.1-local-test.tar.gz*`

- [ ] **Step 5: Run the workflow tests to verify they pass.**

  ```bash
  pytest tests/unit/test_workflows.py::TestPublishWorkflow -v
  ```

  Expected: all five tests PASS.

- [ ] **Step 6: Commit.**

  ```bash
  git add tests/unit/test_workflows.py .github/workflows/publish.yml
  git commit -m "ci: add PyPI publish workflow with scaffold tarball attach"
  ```

---

## Task 7: Create `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md` (repo root)

**Why:** Tell future contributors (and future-you) the commit-message rules that release-please depends on. The full dev install path is added in Plan B; for now, just the Conventional Commits piece.

- [ ] **Step 1: Create `CONTRIBUTING.md`.**

  Write the file with this exact content (note: this block uses 4 backticks as the outer fence so the inner 3-backtick code samples render correctly when you copy-paste):

  ````markdown
  # Contributing to LocalLLM

  ## Commit messages — Conventional Commits

  Every commit on `main` follows [Conventional Commits](https://www.conventionalcommits.org/).
  This is **not** decoration: `release-please` reads commit messages to decide
  when to cut a release and what the next version number is.

  ### Recognized prefixes

  | Prefix         | Version bump (pre-1.0) | Appears in CHANGELOG | Use for |
  |----------------|-----------------------|----------------------|---------|
  | `feat:`        | minor (0.x → 0.(x+1))  | yes, "Features"      | New CLI commands, wizard steps, runtime presets, flags. |
  | `fix:`         | patch (0.x.y → 0.x.(y+1)) | yes, "Bug Fixes"     | Bug fixes. |
  | `perf:`        | patch                  | yes, "Performance"   | Measurable performance improvements. |
  | `docs:`        | none                   | yes, "Documentation" | Documentation changes that affect users. |
  | `feat!:` / `fix!:` / footer `BREAKING CHANGE:` | minor (pre-1.0); will be major post-1.0 | yes, highlighted | Breaking schema/CLI changes. |
  | `chore:` `refactor:` `test:` `ci:` `style:` | none | no (hidden) | Internal changes that don't affect users. |

  ### Examples

  ```text
  feat(serve): add --restart flag to stop+swap configs in one shot
  fix(model-pull): retry idempotently when HF returns 429
  feat!(config): require explicit serve.host (previously defaulted to 0.0.0.0)

  BREAKING CHANGE: existing configs without an explicit `serve.host` will
  refuse to start; add `host: 127.0.0.1` (or your previous default) to fix.
  ```

  ### What if I forget?

  Non-conventional commits are silently ignored by release-please — they
  won't break the build, but they also won't show up in the changelog. If
  you realize mid-PR, rebase / squash to fix; for PRs with many commits,
  use a Conventional-style PR title and ensure "Squash and merge" is the
  merge strategy.

  ## Release flow

  Releases are fully automated:

  1. Merge PRs into `main` using Conventional Commit messages.
  2. `release-please` opens (or updates) a single long-lived **release PR**
     that accumulates the changelog and bumps the version in
     `pyproject.toml` and `src/llm_cli/__init__.py`.
  3. When ready to release, **review the release PR** (it shows you exactly
     what version + changelog will land) and **merge it**.
  4. The merge triggers tag creation, GitHub Release creation, PyPI upload,
     and scaffold-tarball attach. No human action between merge and the
     release going live.

  ## Dev workflow

  _(Coming in Plan B — the layered asset model + `loco update` lands first.)_
  ````

- [ ] **Step 2: Verify the file renders cleanly.**

  Open `CONTRIBUTING.md` in your editor (or run `cat CONTRIBUTING.md | head -40`). Look for unrendered markdown / broken tables.

- [ ] **Step 3: Commit.**

  ```bash
  git add CONTRIBUTING.md
  git commit -m "docs: add CONTRIBUTING with Conventional Commits guide"
  ```

---

## Task 8: Final local verification before pushing

**Files:**
- No new files; verify the whole working tree builds + tests pass.

- [ ] **Step 1: Run the full test suite.**

  ```bash
  python3 -m venv /tmp/final-check
  /tmp/final-check/bin/pip install -e '.[dev]'
  /tmp/final-check/bin/pytest -q
  ```

  Expected: all tests PASS (or `tui` tests skip on non-WSL). The new `test_release_config.py` and `test_workflows.py` should be among the green ones.

- [ ] **Step 2: Build the wheel and sdist one more time.**

  ```bash
  rm -rf dist/ build/ *.egg-info
  /tmp/final-check/bin/python -m build
  /tmp/final-check/bin/twine check dist/*
  rm -rf dist/ build/ *.egg-info /tmp/final-check
  ```

  Expected: both files build, both pass `twine check`.

- [ ] **Step 3: Verify git status is clean.**

  ```bash
  git status
  ```

  Expected: `nothing to commit, working tree clean` (assuming all earlier task commits landed).

- [ ] **Step 4: Inspect the commits you're about to push.**

  ```bash
  git log --oneline origin/main..HEAD
  ```

  Expected: roughly six commits, all Conventional-style (`chore(pyproject):`, `chore(release):`, `ci:`, `docs:`). Eyeball the messages — these will appear in the release PR's commit list (the `chore:` and `ci:` ones will be hidden, but they should still be lint-clean for posterity).

---

## Task 9: Push the plumbing PR and merge to main

**Files:**
- No file changes; a single PR is opened, reviewed, and merged.

- [ ] **Step 1: Push the branch.**

  Decide whether to push directly to `main` or via a PR. For this plan: **via a PR**, because we want the new `ci.yml` workflow to actually run on it.

  ```bash
  git checkout -b ci/release-plumbing
  git push -u origin ci/release-plumbing
  ```

- [ ] **Step 2: Open the PR.**

  ```bash
  gh pr create \
    --title "ci: add release-please, CI, and publish workflows (cut 1)" \
    --body "Implements Cut 1 of docs/superpowers/specs/2026-05-19-update-distribution-and-versioning-design.md.

  No CLI behavior change. Adds:
  - release-please config + workflow
  - pytest + build-check CI on PRs
  - PyPI publish workflow with scaffold tarball + sha256 attach
  - PyPI-friendly pyproject metadata + LICENSE
  - CONTRIBUTING.md with Conventional Commits guide

  Plan B (layered model + loco update + migration) follows after this ships and v0.2.1 smoke-releases successfully."
  ```

- [ ] **Step 3: Watch CI run on the PR.**

  ```bash
  gh pr checks --watch
  ```

  Expected: both `test (3.11)`, `test (3.12)`, and `build-check` succeed. If any fail, fix and push fixup commits to the same branch — DO NOT bypass the failure.

- [ ] **Step 4: Merge the PR.**

  Use squash-merge (so the multiple `chore:` / `ci:` / `docs:` commits collapse into one). The merge commit message should still be Conventional — squash-merging usually picks the PR title, which we set to `ci: add release-please, CI, and publish workflows (cut 1)` — that's fine.

  ```bash
  gh pr merge --squash --delete-branch
  ```

- [ ] **Step 5: Verify release-please ran and the result.**

  ```bash
  gh run list --workflow=release-please.yml --limit 1
  gh pr list --label "autorelease: pending"
  ```

  Expected: a release PR titled something like `chore(main): release 0.2.1` does **not** yet exist — because the merged commit was `ci:`, which release-please ignores. This is correct! No release should fire from infrastructure-only commits.

  (If a release PR did appear, double-check your squash-merge commit message starts with `ci:` not `feat:` or `fix:`.)

---

## Task 10: Smoke-test the pipeline by cutting v0.2.1

**Files:**
- Modify: any small user-visible doc or string that warrants a `fix:` commit. We'll use the README typo route below.

**Why:** Verify end-to-end that a `fix:` commit triggers a release PR, merging it triggers the tag + GitHub Release, and the publish workflow uploads wheel + sdist + scaffold tarball + sha256 correctly to both PyPI and the Release.

- [ ] **Step 1: Pick a tiny `fix:`-worthy change.**

  Suggestion: in `README.md`, fix the section heading drift between the section saying "CLI commands (Milestone 1–2 + lifecycle)" and the actual milestone numbering elsewhere — or fix the most minor typo/punctuation you can find. The goal is a legitimately small, harmless fix.

  Make the change locally. Example:

  ```bash
  # Open README.md, find one tiny defect, fix it.
  ```

- [ ] **Step 2: Commit with a `fix:` message.**

  ```bash
  git checkout -b fix/smoke-test-release
  git add README.md
  git commit -m "fix(docs): correct README phrasing in CLI commands section"
  git push -u origin fix/smoke-test-release
  ```

- [ ] **Step 3: Open a PR and merge it.**

  ```bash
  gh pr create --title "fix(docs): correct README phrasing in CLI commands section" --body "Smoke test commit for the v0.2.1 release pipeline."
  gh pr checks --watch
  gh pr merge --squash --delete-branch
  ```

  Important: the squash-merge commit message must remain `fix(docs): ...`. GitHub's squash UI sometimes prepends `Merge pull request #N from ...`; ensure the result is Conventional.

- [ ] **Step 4: Verify release-please opens the release PR.**

  Wait ~30 seconds, then:

  ```bash
  gh run list --workflow=release-please.yml --limit 1
  gh pr list --label "autorelease: pending"
  ```

  Expected: a release PR titled `chore(main): release 0.2.1` (or similar) exists. Open it in the browser and verify:
  - Version in `pyproject.toml` was bumped 0.2.0 → 0.2.1.
  - Version in `src/llm_cli/__init__.py` was bumped (this is the test of the marker comment from Task 2).
  - `CHANGELOG.md` was created with a "Bug Fixes" section containing your fix.
  - `.release-please-manifest.json` was bumped to `"0.2.1"`.

- [ ] **Step 5: Merge the release PR.**

  Click "Merge pull request" → "Confirm". (Don't squash — release-please's PR should merge as-is with its prepared commit message.)

  Or via CLI:

  ```bash
  RELEASE_PR=$(gh pr list --label "autorelease: pending" --json number --jq '.[0].number')
  gh pr merge "$RELEASE_PR" --merge --delete-branch
  ```

- [ ] **Step 6: Verify the GitHub Release was created.**

  ```bash
  gh release view v0.2.1
  ```

  Expected: a release exists with the changelog body from the merged PR, and the `assets:` section initially empty (the publish workflow hasn't run yet) or already populated if you're a few minutes late.

- [ ] **Step 7: Verify the publish workflow ran and attached all four assets.**

  ```bash
  gh run list --workflow=publish.yml --limit 1
  gh run watch  # if it's still running
  gh release view v0.2.1
  ```

  Expected `assets:` block contains:
  - `localllm_cli-0.2.1-py3-none-any.whl`
  - `localllm_cli-0.2.1.tar.gz` (Python sdist)
  - `scaffold-v0.2.1.tar.gz`
  - `scaffold-v0.2.1.tar.gz.sha256`

  If any are missing, click into the workflow run in the GitHub UI, find the failed step, and triage. The most common first-time failures:
  - **PyPI publish 403 / "trusted publisher not found"** — MP4 wasn't completed or has a typo. Re-check the trusted publisher entry on PyPI's UI.
  - **`gh release upload` 404** — the `contents: write` permission is missing or the tag name lookup is wrong. Verify the workflow's `permissions:` block.
  - **tarball is empty** — `runtimes/`, `configs/`, `benchmarks/`, or `requirements.yaml` weren't where the workflow expected (it `tar`s relative to the checkout root, so that should be fine — but if you reorganized files in Plan B work, this would surface).

- [ ] **Step 8: Verify the wheel landed on PyPI.**

  ```bash
  curl -sI https://pypi.org/pypi/localllm-cli/0.2.1/json | head -n 1
  ```

  Expected: `HTTP/2 200`.

- [ ] **Step 9: Verify the wheel is actually installable.**

  In WSL (clean env):

  ```bash
  python3 -m venv /tmp/install-check
  /tmp/install-check/bin/pip install localllm-cli==0.2.1
  /tmp/install-check/bin/loco --version
  ```

  Expected: `loco 0.2.1`.

  Clean up: `rm -rf /tmp/install-check`

- [ ] **Step 10: Verify the scaffold tarball is downloadable + sha256 matches.**

  ```bash
  cd /tmp
  curl -fLO https://github.com/mtopcu1/local-llm-scaffold/releases/download/v0.2.1/scaffold-v0.2.1.tar.gz
  curl -fLO https://github.com/mtopcu1/local-llm-scaffold/releases/download/v0.2.1/scaffold-v0.2.1.tar.gz.sha256
  sha256sum -c scaffold-v0.2.1.tar.gz.sha256
  tar tzf scaffold-v0.2.1.tar.gz | head -n 20
  cd -
  rm -f /tmp/scaffold-v0.2.1.tar.gz*
  ```

  Expected: `scaffold-v0.2.1.tar.gz: OK` from `sha256sum -c`, and the tar listing shows `runtimes/llamacpp/...`, `configs/...`, `benchmarks/...`, `requirements.yaml` paths.

  This is the critical proof that Plan B's `loco update` command will have valid input to consume.

- [ ] **Step 11: Document the smoke release result.**

  In a follow-up commit (`docs:` so it stays out of CHANGELOG):

  ```bash
  cat >> docs/superpowers/plans/2026-05-19-release-plumbing.md <<'EOF'

  ---

  ## Smoke release record

  - **v0.2.1** released on YYYY-MM-DD.
  - PyPI URL: https://pypi.org/project/localllm-cli/0.2.1/
  - GitHub Release: https://github.com/mtopcu1/local-llm-scaffold/releases/tag/v0.2.1
  - All four assets attached: wheel, sdist, scaffold tarball, sha256. ✓
  - `pipx install localllm-cli==0.2.1` verified working. ✓
  - SHA256 of `scaffold-v0.2.1.tar.gz` verifies against sidecar. ✓
  EOF
  git add docs/superpowers/plans/2026-05-19-release-plumbing.md
  git commit -m "docs(plan): record v0.2.1 smoke release outcome"
  git push
  ```

  Replace `YYYY-MM-DD` with the actual date.

---

## Acceptance criteria for Plan A complete

When all the following are true, Plan A is done:

1. [ ] `release-please-config.json`, `.release-please-manifest.json` exist and are tested.
2. [ ] `.github/workflows/release-please.yml`, `ci.yml`, `publish.yml` exist and are tested.
3. [ ] `pyproject.toml` has full PyPI metadata; `LICENSE` exists; `python -m build` + `twine check dist/*` both succeed.
4. [ ] `src/llm_cli/__init__.py` has the `x-release-please-version` marker.
5. [ ] `CONTRIBUTING.md` exists with the Conventional Commits guide.
6. [ ] `pytest tests/unit/test_release_config.py tests/unit/test_workflows.py` passes.
7. [ ] **v0.2.1 has been smoke-released** with all four assets (wheel, sdist, scaffold tarball, sha256) attached to the GitHub Release and the wheel published to PyPI.
8. [ ] `pipx install localllm-cli==0.2.1` works in a clean env.
9. [ ] `sha256sum -c scaffold-v0.2.1.tar.gz.sha256` passes against the downloaded tarball.

When all nine are checked, **come back here and request Plan B** (layered asset model + `loco update` command + migration script).
