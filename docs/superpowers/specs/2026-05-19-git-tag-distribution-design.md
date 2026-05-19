# LocalLLM Git-Tag Distribution Design

_Date: 2026-05-19_
_Status: Approved — ready for implementation plan_
_Supersedes: `docs/superpowers/specs/2026-05-19-update-distribution-and-versioning-design.md` (PyPI-based distribution)_
_Scope: Replace the PyPI-based install/update model with a curl-installable git-clone pattern modeled on `nousresearch/hermes-agent`. Strip the publish pipeline and asset-tarball machinery._

## 1. Purpose

Make install, update, and CI for LocalLLM dramatically simpler. One install command. One update command. One CI workflow. One release workflow. No PyPI, no wheel publishing, no scaffold-tarball split.

## 2. Problem with the current design

The PyPI-based distribution shipped with three structural problems that we hit in production:

1. **`publish.yml` never fires after a release.** GitHub suppresses workflow triggers (`release: published`) for releases created via `GITHUB_TOKEN`. v0.3.0 and v0.3.1 both shipped with **zero assets** — no wheel on PyPI, no scaffold tarball on the GitHub Release.
2. **Bot-opened release PRs don't get CI checks attached.** Branch protection with required checks blocks the release PR forever; admin bypass is the only way through.
3. **CI re-runs on every push to `main`.** Merging a 4-file release PR runs the full pytest matrix and a no-op `release-please` cycle.

The underlying complexity stack: 3 workflows, 5+ CI jobs, PyPI trusted-publisher setup, scaffold-vs-wheel asset split, version-sync scripts, scaffold-drift detection — all to deliver `pipx install loco-llm-cli`.

`hermes-agent` ships a more popular CLI with a smaller surface: `curl | bash` clones their repo, `hermes update` does `git pull`. No PyPI involved.

## 3. Goals

1. **One-command install** via `curl ... | bash` that clones the repo and sets up an editable install.
2. **`llm update`** that pulls the latest tagged release (or a specified branch/tag) without leaving the user stranded.
3. **Two-workflow CI**: one for PRs (tests), one for release-please (tagging only — no publish job).
4. **Hotfix channel**: `llm update --branch <name>` lets the user (or a power user) switch to a branch tip for a critical fix, with loud warnings that they're off mainline.
5. **No PyPI**, no wheel publishing, no scaffold tarball, no GITHUB_TOKEN trigger gotcha.
6. **Conventional commits + release-please** retained for CHANGELOG and tagging (the parts that work).

## 4. Non-goals

- **No PyPI publishing.** The reserved `loco-llm-cli` name is parked or yanked; we do not ship wheels.
- **No PowerShell native-Windows installer.** WSL2 / Linux / macOS only, matching the current product posture.
- **No scaffold-vs-wheel asset split.** `runtimes/`, `configs/`, `benchmarks/` live in the git clone and update together with code.
- **No prerelease tags by default.** `v1.2.3-rc.1` is skipped unless the user passes `--prerelease` (future work).
- **No automatic detect-and-migrate** from prior pipx installs. One-time manual cleanup is documented.
- **No multi-OS test matrix** in CI. Single Python version, ubuntu-latest. Add back the day a user complains.
- **No `release-pr-check` validation job**, no `check_release_versions.py`, no `build-check`. There is nothing to publish, so nothing to pre-validate.

## 5. Decisions (Q&A trail)

Settled during brainstorming on 2026-05-19:

| Question | Decision |
|---|---|
| Keep PyPI, switch to hermes-style git installer, or hybrid? | **Hermes-style git installer** (Option A). |
| Should `llm update` track `main` or tags? | **Tags only.** Re-anchor to latest stable tag on bare `llm update`. |
| Need a `--branch` flag for hotfixes? | **Yes.** Re-anchor semantics on bare `llm update` brings the user back. |
| Keep release-please? | **Yes**, for CHANGELOG and tagging. Drop the publish job. |
| Native Windows support? | **No.** WSL2 / Linux / macOS only. |
| Big-bang cleanup or incremental? | **One PR.** Pieces are interdependent; solo project; no users to break. |

## 6. Architecture overview

After this design lands, a normal user's machine looks like:

```
~/.loco-llm/                      ← LOCO_LLM_HOME (default), a git clone
├── .git/
├── .venv/                        ← uv-managed venv with editable install
│   └── bin/llm                   ← entry point
├── src/llm_cli/                  ← the CLI code
├── runtimes/                     ← scaffold assets, updated with code
├── configs/
├── benchmarks/
├── pyproject.toml
└── ...

~/.local/bin/llm  →  ~/.loco-llm/.venv/bin/llm   ← symlink on $PATH

~/.config/localllm/settings.yaml         ← user settings (path unchanged)
~/.local/share/localllm/runtime-state/   ← lifecycle records (path unchanged)
```

The git checkout *is* the install. There is no separate scaffold dir, no installed wheel, no PyPI.

## 7. Install flow (`scripts/install.sh`)

Curl-installable one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
```

The script:

1. Verify `git`, Python 3.11+, `curl` are available.
2. Install `uv` if missing (via `astral.sh/uv/install.sh`).
3. Resolve `LOCO_LLM_HOME` (default `$HOME/.loco-llm`, override via env var or `--dir`).
4. If `$LOCO_LLM_HOME` exists and is a clean clone of this repo → treat as upgrade (skip to step 6). Otherwise refuse (don't clobber).
5. `git clone https://github.com/mtopcu1/loco-llm.git "$LOCO_LLM_HOME"`.
6. `git fetch --tags && git checkout <latest semver tag>` (never `main` by default).
7. `uv venv "$LOCO_LLM_HOME/.venv" --python 3.11`.
8. `uv pip install --python "$LOCO_LLM_HOME/.venv" -e "$LOCO_LLM_HOME"`.
9. Ensure `~/.local/bin` exists; symlink `~/.local/bin/llm` → `$LOCO_LLM_HOME/.venv/bin/llm`.
10. Print next-step hint: `run "llm setup" to configure paths`.

Flags accepted (only what we'll actually use):

- `--dir <path>` — override `LOCO_LLM_HOME`
- `--branch <name>` — clone and check out a branch instead of latest tag (for testing/development)
- `--tag <vX.Y.Z>` — clone and pin to a specific tag

Non-goals for the installer:

- No interactive prompts. Pure non-interactive flow.
- No detect-and-migrate from prior pipx install. Document the manual cleanup separately.

## 8. Update flow (`llm update`)

### Surface

```bash
llm update                       # default: latest stable tag (re-anchors if you went off-rails)
llm update --branch <name>       # checkout tip of that branch (the hotfix case)
llm update --tag <vX.Y.Z>        # pin to a specific tag (rollback / testing)
llm update --check               # report current vs. available, no changes
```

### Behavior of bare `llm update` (re-anchor)

```
cd $LOCO_LLM_HOME
git fetch --tags origin
latest_tag := max(tags matching ^v\d+\.\d+\.\d+$)
current := git describe HEAD (tag if exact match, else branch or sha)
if currently on a branch:
    warn: "currently on branch <X>, switching back to latest stable tag <latest_tag>"
if current == latest_tag:
    print "already on latest stable (<latest_tag>)"; return
stash if working tree dirty
git checkout <latest_tag>
uv pip install -e .   # sync deps (cheap if unchanged)
restore stash with warning if it had local changes
print f"updated to {latest_tag}"
```

### Behavior of `--branch <name>`

```
cd $LOCO_LLM_HOME
git fetch origin <name>
if branch missing on origin → error
stash if dirty
git checkout <name>
git pull --ff-only origin <name>
uv pip install -e .
restore stash with warning
print loud warning:
    "you are now on branch <name> — not a stable release.
     run `llm update` to return to latest stable tag."
```

### Refusal modes

- If `LOCO_LLM_HOME` is not a git clone → refuse with "not a managed install".
- If the remote doesn't match the expected `github.com/mtopcu1/loco-llm` → refuse with override instructions.
- If a dev sentinel file (e.g. `.loco-dev`) exists at the root → refuse with "this looks like a dev checkout, use `git pull` yourself."

### Visibility

- `llm --version` shows `loco-llm 0.4.2` on a tag, `loco-llm 0.4.2-7+gabc1234 (branch: hotfix/foo)` off-tag.
- `llm doctor` adds a check: if HEAD is not an exact tag match, print a yellow warning with the re-anchor command.

### Hotfix flow (worked example)

```bash
# something breaks in v0.4.1; you push hotfix/scaffold-perms to origin

# on the affected machine:
llm update --branch hotfix/scaffold-perms
# warning: you are now on branch hotfix/scaffold-perms — not a stable release.

# fix verified, you open PR, merge, release-please cuts v0.4.2

llm update
# currently on branch hotfix/scaffold-perms, switching back to latest stable tag v0.4.2
# updated to v0.4.2
```

## 9. CI (`.github/workflows/ci.yml`)

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
      - run: uv venv && uv pip install -e ".[dev]"
      - run: uv run pytest -q
```

Baked-in choices:

- **PR only.** No CI on push to `main`. The PR already passed; re-running is wasteful and was the root cause of the "why did CI run again?" pain.
- **Single Python version (3.11).** Matrix is over-engineering for a solo pre-1.0 project.
- **Skip release-please PRs.** They only touch version/CHANGELOG files.
- **`uv` in CI** for parity with the install path and speed.

## 10. Release (`.github/workflows/release-please.yml`)

```yaml
name: release-please
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

**No publish job. No PyPI. No tarball. No asset attach.**

What this workflow does:

1. Watches conventional commits on `main`.
2. Opens / updates a single long-lived release PR containing CHANGELOG + version bump in `pyproject.toml` and `src/llm_cli/__init__.py`.
3. When the release PR merges → creates git tag `vX.Y.Z` and a GitHub Release with the CHANGELOG body.

`llm update` finds the tag on its next run. That is the publish.

## 11. Branch protection on `main`

- Required check: `test` (single check, from `ci.yml`).
- Admin bypass enabled — used to merge release PRs (bot PRs don't get checks attached; this is structural in GitHub).
- Conventional commits enforced socially via:
  - `.cursor/rules/conventional-commits.mdc` (already present)
  - `CONTRIBUTING.md` (already present)

## 12. Developer loop

```
feature branch
  → PR ───→ ci.yml runs tests ───→ green ───→ merge
                                                 │
                                                 ▼
                                    release-please.yml on main
                                                 │
                                       ┌─────────┴──────────┐
                                       ▼                    ▼
                            updates release PR        (nothing else)
                                       │
                                       ▼
                          merge release PR (admin OK)
                                       │
                                       ▼
                          tag vX.Y.Z + GitHub Release + CHANGELOG
                                       │
                                       ▼
                          users run `llm update` → picks up tag
```

## 13. Burn-down list

### Delete outright

| File | Reason |
|---|---|
| `.github/workflows/publish.yml` | No PyPI publish |
| `scripts/install-dev.sh` | Dev install is `git clone && uv pip install -e .` — document, don't script |
| `scripts/migrate-from-v0.2.sh` | Pre-PyPI migration helper, irrelevant in new model |
| `scripts/check_release_versions.py` | Was for `release-pr-check`; deleted |
| `src/llm_cli/core/update_check.py` | Fetches PyPI version — no PyPI |
| `src/llm_cli/core/scaffold_update.py` | Scaffold tarball install/rollback — no tarball |
| `src/llm_cli/core/scaffold_drift.py` | CLI-vs-scaffold version drift detection — same version now |
| `tests/unit/test_update_check.py` | Tests deleted module |
| `tests/unit/test_scaffold_update.py`, `test_scaffold_drift.py` | Tests deleted modules |

### Rewrite

| File | New behavior |
|---|---|
| `scripts/install.sh` | Curl one-liner: clone → checkout latest tag → uv venv → editable install → symlink |
| `src/llm_cli/commands/update_cmd.py` | git-based update with re-anchor semantics + `--branch` / `--tag` / `--check` |
| `.github/workflows/ci.yml` | Per section 9 |
| `.github/workflows/release-please.yml` | Per section 10 (no publish job) |
| `tests/unit/test_update_cmd.py` | Coverage for git-based update flow |
| `tests/unit/test_workflows.py` | Slim to shape checks for `ci` + `release-please` only |
| `README.md` | curl install one-liner; `llm update`; remove all `pipx install` references |
| `CONTRIBUTING.md` | Drop PyPI section; keep conventional commits |
| `docs/RELEASE_SETUP.md` | Reduce to: enable Actions PR creation + branch protection note |

### Repurpose

| File | Change |
|---|---|
| `src/llm_cli/core/scaffold.py` | `scaffold_root()` returns `LOCO_LLM_HOME` (the git checkout). Callers unchanged. |
| `pyproject.toml` | Drop `twine` from `[dev]`. Keep `build` as optional sanity tool. Keep package metadata for editable install hygiene. |

### Keep untouched

- All `runtime/`, `model/`, `config/`, `serve/`, `doctor/`, `setup/`, `settings/`, `lifecycle/` code.
- `runtimes/`, `configs/`, `benchmarks/`.
- `release-please-config.json`, `.release-please-manifest.json`.
- The Cursor `conventional-commits` rule.
- User data paths (`~/.config/localllm/`, `~/.local/share/localllm/`).

## 14. Migration for existing installs

You currently have (or may have) `loco-llm-cli` installed via pipx from the old PyPI flow. One-time manual cleanup, documented in README "Upgrading":

```bash
pipx uninstall loco-llm-cli   # or: pip uninstall loco-llm-cli
rm -f ~/.local/bin/llm
curl -fsSL https://raw.githubusercontent.com/mtopcu1/loco-llm/main/scripts/install.sh | bash
```

The new installer does **not** auto-detect-and-migrate. Effectively a single user (the maintainer); no need for migration code.

User data (`~/.config/localllm/settings.yaml`, `~/.local/share/localllm/`) is untouched by the migration. Settings and runtime state carry over.

## 15. PyPI loose end

- Any PyPI project name reserved for this project (`loco-llm-cli`, `locallm-cli`, or similar) is parked. We do not push to it.
- Optional follow-up: yank entirely, or push a single `0.0.0` placeholder with a deprecation notice pointing to the GitHub install instructions.
- Trusted-publisher entries on PyPI for our workflows can be deleted in the same pass.

## 16. Smoke test plan (after implementation)

1. Merge the rewrite PR (will contain a `feat!:` breaking-change commit → minor or major bump per pre-1.0 semantics).
2. Merge the release-please-generated release PR → tag `vX.Y.0` created.
3. In a fresh WSL2 environment: run the curl one-liner; verify `llm --version` returns the new tag.
4. Run `llm update` — should report "already on latest stable".
5. Push a trivial `fix:` commit, merge, merge the new release PR → tag `vX.Y.1`.
6. Run `llm update` on the test machine — should pull `vX.Y.1`.
7. Test the hotfix path: push a branch, `llm update --branch <name>` from the test machine, verify warning, then bare `llm update` to re-anchor.

## 17. Open implementation questions

(These are for the writing-plans phase, not the spec.)

- Exact mechanics of `scaffold_root()` returning `LOCO_LLM_HOME` — what env vars / fallbacks?
- Stash policy precise text and failure handling.
- Whether to also gate `llm update` behind a `--yes` confirmation (or default to non-interactive).
- Whether `llm update --check` should exit non-zero when behind (CI-friendly) or zero (informational).

## 18. Out of scope (deliberately)

- Multi-channel updates (`--prerelease`, `--unstable`).
- PowerShell installer.
- Compile-to-binary distribution.
- Automatic post-update verification beyond `llm --version`.
- Rolling back from a bad tag (manual: `llm update --tag <prev>`).

---

**This spec supersedes the previous PyPI-based distribution design.** The implementation plan derived from this spec will live at `docs/superpowers/plans/2026-05-19-git-tag-distribution.md`.
